"""Adopt or plan/apply existing production resources without publishing state/plans.

Runs only on a manually dispatched main-branch GitHub Actions job. Terraform state
lives in an HCP Local-execution workspace. No cloud create/delete is permitted here.
"""
import hashlib
import json
import os
import re
from urllib.parse import unquote, urlsplit
from build_render_provider import UPSTREAM_COMMIT, ARCHIVE_SHA256, PATCHES
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2] / "infra" / "terraform"
RESOURCES = {
    "neon_project.production": "NEON_PROJECT_ID",
    "render_web_service.app": "RENDER_SERVICE_ID",
}


def init_diagnostics(output):
    """Read structured Terraform errors, never state, plan data or source excerpts."""
    secrets = []
    for name in ("TF_TOKEN_app_terraform_io", "RENDER_API_KEY", "NEON_API_KEY", "TF_VAR_database_url", "TF_VAR_additional_render_env_vars"):
        value = os.environ.get(name)
        if value:
            secrets.append(value)
    database = os.environ.get("TF_VAR_database_url", "")
    if database:
        try:
            password = urlsplit(database).password
            if password:
                secrets.extend([password, unquote(password)])
        except ValueError:
            pass
    extra = os.environ.get("TF_VAR_additional_render_env_vars", "{}")
    try:
        secrets.extend(value for value in json.loads(extra).values() if isinstance(value, str) and value)
    except (json.JSONDecodeError, AttributeError):
        pass
    messages = []
    for line in output.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        diagnostic = event.get("diagnostic", {})
        if diagnostic.get("severity") != "error":
            continue
        # Omit source snippets, resource data and all unrelated JSON fields.
        # Mask input credentials and provider cty string-value dumps.
        message = diagnostic.get("summary", "Initialization error") + "\n" + diagnostic.get("detail", "")
        for secret in sorted(set(secrets), key=len, reverse=True):
            message = message.replace(secret, "[REDACTED]")
        message = re.sub(r"(?i)(postgres(?:ql)?(?:\+asyncpg)?://)[^\s]+", r"\1[REDACTED]", message)
        message = re.sub(r"(?i)(bearer\s+)\S+", r"\1[REDACTED]", message)
        message = re.sub(r'cty\.StringVal\("(?:[^"\\]|\\.)*"\)', 'cty.StringVal("[REDACTED]")', message)
        messages.append(message[:3000])
    return "\n".join(messages[:3])


def terraform(*args):
    result = subprocess.run(["terraform", *args], cwd=ROOT, capture_output=True, text=True)
    if result.returncode:
        # Provider diagnostics can contain remote data. Do not echo captured logs,
        # state, or plan JSON into a public repository's workflow logs.
        details = init_diagnostics(result.stdout + "\n" + result.stderr) if args[0] in {"init", "apply"} else ""
        message = f"terraform {args[0]} failed (exit {result.returncode})"
        raise RuntimeError(message + ("\n" + details if details else "; check configuration, credentials, and HCP workspace settings"))
    return result.stdout


def plan_summary(plan):
    changes = plan.get("resource_changes", [])
    for item in changes:
        if item.get("mode") != "managed":
            continue
        if item["address"] not in RESOURCES:
            raise RuntimeError("Plan contains an unexpected resource")
        if not set(item["change"]["actions"]).issubset({"no-op", "update"}):
            raise RuntimeError("Refusing a plan that creates, deletes, or replaces resources")
    # Hash the actual intended changes, including sensitive values, without
    # printing them. Ignore run timestamps so a fresh identical plan can match.
    payload = {key: plan.get(key, {}) for key in ("resource_changes", "output_changes")}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    lines = ["### Production Terraform plan", ""]
    for item in changes:
        change = item["change"]
        lines.append(f"- `{item['address']}`: {', '.join(change['actions'])}")
        before, after = change.get("before") or {}, change.get("after") or {}
        # Show field names for all differences. Only these known nonsecret
        # scalar settings get values; imported provider state can contain secrets.
        public_fields = {"name", "plan", "region", "health_check_path", "num_instances",
                         "pg_version", "region_id", "history_retention_seconds", "root_directory", "slug"}
        for key in sorted(before.keys() | after.keys()):
            if before.get(key) == after.get(key):
                continue
            if key == "env_vars":
                old_vars, new_vars = before.get(key) or {}, after.get(key) or {}
                for name in sorted(old_vars.keys() | new_vars.keys()):
                    if old_vars.get(name) != new_vars.get(name):
                        action = "removed" if name not in new_vars else "added" if name not in old_vars else "updated"
                        if name == "APP_ORIGIN":
                            old_origin = (old_vars.get(name) or {}).get("value")
                            new_origin = (new_vars.get(name) or {}).get("value")
                            def public_origin(value):
                                if value is None:
                                    return None
                                parsed = urlsplit(value)
                                return value if parsed.scheme in {"http", "https"} and parsed.hostname and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment and parsed.path in {"", "/"} else "[withheld: not a plain origin]"
                            lines.append(f"  - environment APP_ORIGIN: {json.dumps(public_origin(old_origin))} → {json.dumps(public_origin(new_origin))}")
                        else:
                            lines.append(f"  - environment `{name}`: {action} (value withheld)")
            elif key == "runtime_source":
                old_docker = (before.get(key) or {}).get("docker") or {}
                new_docker = (after.get(key) or {}).get("docker") or {}
                fields = {"branch", "context", "dockerfile_path", "auto_deploy", "auto_deploy_trigger", "repo_url"}
                for field in sorted(fields):
                    if old_docker.get(field) != new_docker.get(field):
                        old_value, new_value = old_docker.get(field), new_docker.get(field)
                        if field == "repo_url":
                            def public_repo(value):
                                if value is None:
                                    return None
                                parsed = urlsplit(value)
                                return value if parsed.scheme == "https" and parsed.hostname == "github.com" and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment else "[withheld]"
                            old_value, new_value = public_repo(old_value), public_repo(new_value)
                        lines.append(f"  - docker.{field}: {json.dumps(old_value)} → {json.dumps(new_value)}")
            elif key in public_fields:
                destination = "(known after apply)" if change.get("after_unknown", {}).get(key) is True else json.dumps(after.get(key))
                lines.append(f"  - {key}: {json.dumps(before.get(key))} → {destination}")
            else:
                lines.append(f"  - {key}: changed (values withheld; inspect the committed configuration)")
    lines += ["", f"Plan fingerprint: `{digest}`", "", "No secret values or plan files are uploaded."]
    return digest, "\n".join(lines) + "\n"


def activate_render_provider():
    """Use only the checksum-verified compatibility build from this workflow."""
    directory = Path(os.environ.get("RENDER_PROVIDER_DIR", "/nonexistent-provider")).resolve()
    manifest = directory / "build.json"
    binary = directory / "terraform-provider-render"
    if not manifest.is_file() or not binary.is_file():
        raise RuntimeError("Build the Render free-tier compatibility provider before running production Terraform")
    metadata = json.loads(manifest.read_text())
    expected = {
        "upstream_commit": UPSTREAM_COMMIT,
        "archive_sha256": ARCHIVE_SHA256,
        "patch_sha256": hashlib.sha256((PATCHES / "render-free-tier.patch").read_bytes()).hexdigest(),
        "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
    }
    if metadata != expected:
        raise RuntimeError("Render compatibility provider verification failed")
    os.environ["TF_CLI_CONFIG_FILE"] = str(directory / "terraform.tfrc")


def main():
    action = os.environ["INFRA_ACTION"]
    if action not in {"import", "plan", "apply"}:
        raise RuntimeError("Unknown infrastructure action")
    required = ["RENDER_API_KEY", "RENDER_OWNER_ID", "NEON_API_KEY", "TF_TOKEN_app_terraform_io",
                "TF_CLOUD_ORGANIZATION", "TF_WORKSPACE", "TF_VAR_database_url",
                "TF_VAR_render_service_name", "TF_VAR_render_region", "TF_VAR_app_origin",
                "TF_VAR_neon_project_name", *RESOURCES.values()]
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError("Missing GitHub environment settings: " + ", ".join(missing))
    terraform("init", "-json", "-input=false", "-lockfile=readonly")
    activate_render_provider()
    terraform("validate")
    for address, id_variable in RESOURCES.items():
        # Re-read because the previous import updates state. Never print it.
        state = json.loads(terraform("show", "-json"))
        managed = {item["address"]: item for item in state.get("values", {}).get("root_module", {}).get("resources", [])}
        if address not in managed:
            if action != "import":
                raise RuntimeError(f"Import {address} first using the import action")
            terraform("import", "-input=false", "-lock-timeout=120s", address, os.environ[id_variable])
        elif managed[address]["values"]["id"] != os.environ[id_variable]:
            raise RuntimeError(f"Existing state for {address} does not match the configured resource ID")
    if action == "import":
        # Import is deliberately separate from any plan/apply and is safe to
        # retry if the second import failed. It changes state only.
        print("Existing Neon project and Render service adopted. No infrastructure changes applied. Run plan next.")
        return
    with tempfile.TemporaryDirectory(prefix="production-plan-") as temporary:
        saved = str(Path(temporary) / "production.tfplan")
        terraform("plan", "-input=false", "-lock-timeout=120s", "-out=" + saved)
        digest, summary = plan_summary(json.loads(terraform("show", "-json", saved)))
        print(summary)
        if target := os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(target, "a") as output:
                output.write(summary)
        if action == "apply":
            if os.environ.get("EXPECTED_PLAN_SHA", "").strip() != digest:
                raise RuntimeError("Plan differs from the reviewed fingerprint. Review this new plan and rerun apply with its fingerprint")
            terraform("apply", "-json", "-input=false", "-lock-timeout=120s", saved)
            print("Applied the reviewed plan. Render configuration changes may trigger a deployment.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
