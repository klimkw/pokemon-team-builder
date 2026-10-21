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


if __name__ == '__main__':
    unittest.main()
