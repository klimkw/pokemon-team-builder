"""Build one audited compatibility patch on a checksum-pinned upstream provider.

No cloud credentials are needed. Only Terraform's provider executable is changed;
the resource schema, resource IDs, lockfile, and state format stay at v1.9.1.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request

UPSTREAM_COMMIT = "1a3083da847fb55796947866506bc79671a4dc31"
ARCHIVE_SHA256 = "e4fe981383983593ad12a1f424159545dcda92fbcb37a4da3713e5e7ccbfc164"
PATCHES = Path(__file__).resolve().parent / "provider-patches"


def build(destination):
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    archive = urllib.request.urlopen(
        "https://codeload.github.com/render-oss/terraform-provider-render/tar.gz/" + UPSTREAM_COMMIT,
        timeout=60,
    ).read()
    if hashlib.sha256(archive).hexdigest() != ARCHIVE_SHA256:
        raise RuntimeError("Upstream provider source checksum mismatch")
    # No cloud credentials are passed to the compiler or provider test process.
    build_env = {key: value for key, value in os.environ.items()
                 if key not in {"RENDER_API_KEY", "NEON_API_KEY", "TF_TOKEN_app_terraform_io"}
                 and not key.startswith("TF_VAR_")}
    build_env.update({"CGO_ENABLED": "0", "GOTOOLCHAIN": "local"})
    with tempfile.TemporaryDirectory(prefix="render-provider-source-") as temporary:
        root = Path(temporary)
        with tarfile.open(fileobj=io.BytesIO(archive)) as source:
            for member in source.getmembers():
                path = Path(*Path(member.name).parts[1:])
                if not member.isfile() or not path.parts:
                    continue
                target = (root / path).resolve()
                if not target.is_relative_to(root):
                    raise RuntimeError("Unsafe source archive path")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.extractfile(member).read())
        subprocess.run(["git", "apply", "--check", str(PATCHES / "render-free-tier.patch")], cwd=root, env=build_env, check=True)
        subprocess.run(["git", "apply", str(PATCHES / "render-free-tier.patch")], cwd=root, env=build_env, check=True)
        shutil.copyfile(PATCHES / "free_tier_test.go", root / "internal/provider/webservice/resource/internal/pokemon_free_tier_test.go")
        subprocess.run(["go", "test", "-mod=readonly", "./internal/provider/webservice/resource/internal", "-run", "TestPokemonFreeTierMaintenancePayload", "-count=1", "-v"], cwd=root, env=build_env, check=True)
        subprocess.run(["go", "build", "-mod=readonly", "-trimpath", "-ldflags=-s -w -X main.version=1.9.1", "-o", str(destination / "terraform-provider-render"), "."], cwd=root, env=build_env, check=True)
    metadata = {
        "upstream_commit": UPSTREAM_COMMIT,
        "archive_sha256": ARCHIVE_SHA256,
        "patch_sha256": hashlib.sha256((PATCHES / "render-free-tier.patch").read_bytes()).hexdigest(),
        "binary_sha256": hashlib.sha256((destination / "terraform-provider-render").read_bytes()).hexdigest(),
    }
    (destination / "build.json").write_text(json.dumps(metadata, indent=2) + "\n")
    config = 'provider_installation {\n  dev_overrides {\n    "registry.terraform.io/render-oss/render" = ' + json.dumps(str(destination)) + '\n  }\n  direct {}\n}\n'
    (destination / "terraform.tfrc").write_text(config)
    print("Built Render 1.9.1 with the free-tier maintenanceMode PATCH fix.")


if __name__ == "__main__":
    target = os.environ.get("RENDER_PROVIDER_DIR", str(Path(tempfile.gettempdir()) / "pokemon-render-provider"))
    build(target)
