"""Protect the adoption/apply boundary without cloud accounts."""
import unittest
from unittest.mock import patch
from production import plan_summary, main


def plan(actions=None, address='render_web_service.app', value='dummy-secret'):
    return {'resource_changes': [{'address': address, 'mode': 'managed',
            'change': {'actions': actions or ['update'], 'before': {'value': 'before'}, 'after': {'value': value}}}]}


class PlanPolicyTests(unittest.TestCase):
    def test_updates_are_reviewable_without_printing_secrets(self):
        fingerprint, summary = plan_summary(plan())
        self.assertEqual(len(fingerprint), 64)
        self.assertIn('render_web_service.app', summary)
        self.assertNotIn('dummy-secret', summary)

    def test_sensitive_change_invalidates_review_fingerprint(self):
        first, _ = plan_summary(plan(value='one'))
        second, _ = plan_summary(plan(value='two'))
        self.assertNotEqual(first, second)

    def test_run_timestamps_do_not_invalidate_unchanged_plan(self):
        first = plan()
        second = {**first, 'timestamp': 'another-run'}
        self.assertEqual(plan_summary(first)[0], plan_summary(second)[0])

    def test_creates_deletes_and_replacements_are_rejected(self):
        for actions in [['create'], ['delete'], ['delete', 'create']]:
            with self.subTest(actions=actions), self.assertRaises(RuntimeError):
                plan_summary(plan(actions))

    def test_unexpected_resources_are_rejected(self):
        with self.assertRaises(RuntimeError):
            plan_summary(plan(address='neon_project.unexpected'))

    def test_public_render_differences_are_visible_but_database_url_is_hidden(self):
        change = plan()
        change['resource_changes'][0]['change'] = {
            'actions': ['update'],
            'before': {'env_vars': {'APP_ORIGIN': {'value': 'https://old.example'}, 'DATABASE_URL': {'value': 'private-old'}}},
            'after': {'env_vars': {'APP_ORIGIN': {'value': 'https://new.example'}, 'DATABASE_URL': {'value': 'private-new'}}, 'runtime_source': {'docker': {'context': '.', 'repo_url': 'private-repo-credential'}}},
        }
        _, summary = plan_summary(change)
        self.assertIn('https://old.example', summary)
        self.assertIn('https://new.example', summary)
        self.assertIn('docker.context', summary)
        self.assertNotIn('private-old', summary)
        self.assertNotIn('private-new', summary)
        self.assertNotIn('private-repo-credential', summary)

    def test_origin_with_credentials_is_withheld(self):
        change = plan()
        change['resource_changes'][0]['change']['after'] = {'env_vars': {'APP_ORIGIN': {'value': 'https://user:private-password@host'}}}
        _, summary = plan_summary(change)
        self.assertNotIn('private-password', summary)

    def test_missing_settings_fail_before_running_terraform(self):
        with patch.dict('os.environ', {'INFRA_ACTION': 'import'}, clear=True), patch('production.terraform') as run:
            with self.assertRaisesRegex(RuntimeError, 'Missing GitHub'):
                main()
            run.assert_not_called()

class AdoptionBoundaryTests(unittest.TestCase):
    def environment(self, action):
        from production import RESOURCES
        names = ['RENDER_API_KEY', 'RENDER_OWNER_ID', 'NEON_API_KEY', 'TF_TOKEN_app_terraform_io',
                 'TF_CLOUD_ORGANIZATION', 'TF_WORKSPACE', 'TF_VAR_database_url',
                 'TF_VAR_render_service_name', 'TF_VAR_render_region', 'TF_VAR_app_origin',
                 'TF_VAR_neon_project_name', *RESOURCES.values()]
        return {**dict.fromkeys(names, 'dummy'), 'INFRA_ACTION': action}

    def state(self):
        from production import RESOURCES
        import json
        return json.dumps({'values': {'root_module': {'resources': [
            {'address': address, 'values': {'id': 'dummy'}} for address in RESOURCES]}}})

    def test_import_with_existing_ids_never_applies(self):
        with patch.dict('os.environ', self.environment('import'), clear=True), patch('production.terraform') as run:
            run.side_effect = lambda *args: self.state() if args[0] == 'show' else ''
            main()
            self.assertFalse(any(call.args[0] in {'import', 'plan', 'apply'} for call in run.call_args_list))

    def test_wrong_state_id_stops_adoption(self):
        env = {**self.environment('import'), 'RENDER_SERVICE_ID': 'wrong-id'}
        with patch.dict('os.environ', env, clear=True), patch('production.terraform') as run:
            run.side_effect = lambda *args: self.state() if args[0] == 'show' else ''
            with self.assertRaisesRegex(RuntimeError, 'does not match'):
                main()
            self.assertFalse(any(call.args[0] == 'apply' for call in run.call_args_list))

    def test_unreviewed_plan_cannot_apply(self):
        import json
        def output(*args):
            if args[0] == 'show':
                return json.dumps(plan()) if len(args) > 2 else self.state()
            return ''
        with patch.dict('os.environ', self.environment('apply'), clear=True), patch('production.terraform', side_effect=output) as run:
            with self.assertRaisesRegex(RuntimeError, 'fingerprint'):
                main()
            self.assertFalse(any(call.args[0] == 'apply' for call in run.call_args_list))


class InitializationDiagnosticTests(unittest.TestCase):
    def test_init_error_explains_hcp_failure_without_credentials(self):
        import json
        from production import init_diagnostics
        event = {"diagnostic": {"severity": "error", "summary": "Failed to read organization", "detail": "Unauthorized: Bearer secret-token; postgresql://user:encoded%40password@host/db", "snippet": "never print source"}}
        with patch.dict('os.environ', {'TF_TOKEN_app_terraform_io': 'secret-token', 'TF_VAR_database_url': 'postgresql://user:encoded%40password@host/db'}, clear=True):
            message = init_diagnostics(json.dumps(event))
        self.assertIn('Failed to read organization', message)
        self.assertIn('Unauthorized', message)
        self.assertNotIn('secret-token', message)
        self.assertNotIn('encoded%40password', message)
        self.assertNotIn('never print source', message)

    def test_unstructured_logs_and_non_errors_are_not_exposed(self):
        import json
        from production import init_diagnostics
        output = 'raw private provider data\n' + json.dumps({'diagnostic': {'severity': 'warning', 'detail': 'private'}})
        self.assertEqual(init_diagnostics(output), '')


class ApplyDiagnosticTests(unittest.TestCase):
    def test_provider_error_withholds_cty_string_values_and_extra_credentials(self):
        import json
        from production import init_diagnostics
        detail = 'root_directory: was null, but now cty.StringVal("private-state-value"). Extra: extra-credential'
        output = json.dumps({'diagnostic': {'severity': 'error', 'summary': 'Provider produced inconsistent result after apply', 'detail': detail}})
        with patch.dict('os.environ', {'TF_VAR_additional_render_env_vars': '{"EXTRA":"extra-credential"}'}, clear=True):
            message = init_diagnostics(output)
        self.assertIn('root_directory', message)
        self.assertIn('Provider produced inconsistent result', message)
        self.assertNotIn('private-state-value', message)
        self.assertNotIn('extra-credential', message)

    def test_failed_apply_exposes_structured_error(self):
        import json
        from types import SimpleNamespace
        from production import terraform
        diagnostic = json.dumps({'diagnostic': {'severity': 'error', 'summary': 'Render rejected update', 'detail': 'API returned HTTP 400'}})
        with patch('production.subprocess.run', return_value=SimpleNamespace(returncode=1, stdout=diagnostic, stderr='raw private logs')):
            with self.assertRaisesRegex(RuntimeError, 'Render rejected update') as error:
                terraform('apply', '-json', 'saved.tfplan')
        self.assertNotIn('raw private logs', str(error.exception))


if __name__ == '__main__':
    unittest.main()
