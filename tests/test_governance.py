import json
from pathlib import Path
import tempfile
import unittest

from hypersearch.governance import check


class GovernanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.files = {
            'pyproject.toml': '[project]\nversion = "0.1.0"\n',
            'src/hypersearch/__init__.py': '__version__ = "0.1.0"\n',
            '.github/workflows/tests.yml': 'steps:\n  - uses: actions/checkout@' + 'a' * 40 + '\n',
            'governance/release.json': json.dumps({
                'schema': 'hypersearch.release/v1', 'version': '0.1.0',
                'api': 'hypersearch.api/v1', 'status': 'development',
                'schemas': ['hypersearch.task/v1'],
                'verifiers': ['hypersearch.zero-sum-subsets/v1']}),
        }
        for path, content in self.files.items():
            self.write(path, content)
        self.paths = list(self.files) + ['governance/materials.json']
        self.rows = [{'path': p, 'owner': 'maintainers', 'role': 'configuration',
                      'lifecycle': 'active'} for p in self.paths]
        self.manifest()

    def write(self, path, content):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

    def manifest(self):
        self.write('governance/materials.json', json.dumps({
            'schema': 'hypersearch.materials/v1', 'materials': self.rows}))

    def errors(self):
        return check(self.root, self.paths)

    def test_valid_inventory_and_release(self):
        self.assertEqual(self.errors(), [])

    def test_missing_unregistered_and_duplicate_material(self):
        self.write('new.md', '# Unregistered')
        self.paths.append('new.md')
        self.assertTrue(any('unregistered' in e for e in self.errors()))
        self.rows.append(self.rows[0].copy())
        self.manifest()
        self.assertTrue(any('duplicate material' in e for e in self.errors()))
        (self.root / 'pyproject.toml').unlink()
        self.assertTrue(any('missing' in e for e in self.errors()))

    def test_registered_but_not_tracked(self):
        self.rows.append({'path': 'stale.md', 'owner': 'maintainers',
                          'role': 'documentation', 'lifecycle': 'archived'})
        self.manifest()
        self.assertTrue(any('not tracked' in e for e in self.errors()))

    def test_version_drift_and_mutable_action(self):
        self.write('src/hypersearch/__init__.py', '__version__ = "0.2.0"\n')
        self.write('.github/workflows/tests.yml', 'steps:\n  - uses: actions/checkout@v4\n')
        errors = self.errors()
        self.assertTrue(any('version differs' in e for e in errors))
        self.assertTrue(any('immutable' in e for e in errors))

    def test_quoted_and_inline_action_references(self):
        self.write('.github/workflows/tests.yml', "steps:\n  - 'uses': actions/checkout@v4\n")
        self.assertTrue(any('immutable' in e for e in self.errors()))
        self.write('.github/workflows/tests.yml', "steps:\n  - {uses: actions/checkout@v4}\n")
        self.assertTrue(any('unsupported inline' in e for e in self.errors()))

    def test_invalid_path_owner_and_schema(self):
        self.rows[0]['path'] = '../outside'
        self.manifest()
        self.assertTrue(any('invalid material path' in e for e in self.errors()))
        self.rows[0]['path'] = self.paths[0]
        self.rows[0]['owner'] = ''
        self.manifest()
        self.assertTrue(any('owner' in e for e in self.errors()))
        self.write('governance/release.json', '{}')
        self.assertTrue(any('release manifest' in e for e in self.errors()))

    def test_symlink_and_duplicate_json_key_rejected(self):
        target = self.root / 'src/hypersearch/__init__.py'
        target.unlink()
        target.symlink_to(self.root / 'pyproject.toml')
        self.assertTrue(any('symlink' in e for e in self.errors()))
        self.write('governance/materials.json', '{"schema":"a","schema":"b"}')
        self.assertTrue(any('duplicate JSON key' in e for e in self.errors()))

    def test_invalid_tracked_path_and_unversioned_schema(self):
        self.assertTrue(check(self.root, ['../outside']))
        release = json.loads(self.files['governance/release.json'])
        release['schemas'] = ['unversioned']
        self.write('governance/release.json', json.dumps(release))
        self.assertTrue(any('versioned identities' in e for e in self.errors()))


if __name__ == '__main__':
    unittest.main()
