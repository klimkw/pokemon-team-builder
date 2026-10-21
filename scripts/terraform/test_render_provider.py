"""Reject an unexpected provider build before cloud operations use it."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from demo import activate_render_provider
from build_render_provider import UPSTREAM_COMMIT, ARCHIVE_SHA256, PATCHES


class ProviderVerificationTests(unittest.TestCase):
    def test_missing_compatibility_build_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'RENDER_PROVIDER_DIR': directory}):
            with self.assertRaisesRegex(RuntimeError, 'Build the Render'):
                activate_render_provider()

    def test_tampered_binary_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'RENDER_PROVIDER_DIR': directory}):
            root = Path(directory)
            (root / 'terraform-provider-render').write_bytes(b'changed')
            (root / 'build.json').write_text(json.dumps({
                'upstream_commit': UPSTREAM_COMMIT,
                'archive_sha256': ARCHIVE_SHA256,
                'patch_sha256': hashlib.sha256((PATCHES / 'render-free-tier.patch').read_bytes()).hexdigest(),
                'binary_sha256': hashlib.sha256(b'original').hexdigest(),
            }))
            with self.assertRaisesRegex(RuntimeError, 'verification failed'):
                activate_render_provider()


if __name__ == '__main__':
    unittest.main()
