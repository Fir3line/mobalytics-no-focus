import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

import patch_mobalytics as app


class SafetyTests(unittest.TestCase):
    def make_archive(self, folder, corrupt=False):
        content = b'fictional test content'
        entry = {'size': len(content), 'offset': '0',
                 'integrity': {'hash': hashlib.sha256(content).hexdigest()}}
        header = {'files': {'build': {'files': {'src_lol_bootstrap_ts.js': entry}}}}
        raw = json.dumps(header).encode()
        path = folder / 'test.asar'
        prefix = struct.pack('<4I', 4, len(raw) + 8, len(raw) + 4, len(raw))
        path.write_bytes(prefix + raw + (b'X' + content[1:] if corrupt else content))
        return path, content

    def test_valid_archive(self):
        with tempfile.TemporaryDirectory() as temp:
            path, content = self.make_archive(Path(temp))
            self.assertEqual(app.archive_info(path)[3], content)

    def test_corrupted_entry_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path, _ = self.make_archive(Path(temp), corrupt=True)
            with self.assertRaisesRegex(RuntimeError, 'integrity'):
                app.archive_info(path)

    def test_unknown_install_is_not_backed_up_or_modified(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            exe, archive = root / 'app.exe', root / 'app.asar'
            exe.write_bytes(b'unknown executable')
            archive.write_bytes(b'unknown archive')
            backup = root / 'backup'
            with patch.multiple(app, ROOT=backup, EXE=exe, ASAR=archive):
                with self.assertRaisesRegex(RuntimeError, 'Unknown'):
                    app.ensure_backups('do')
            self.assertFalse(backup.exists())
            self.assertEqual(exe.read_bytes(), b'unknown executable')
            self.assertEqual(archive.read_bytes(), b'unknown archive')

    def test_partial_backups_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            saved = root / 'app.asar.original'
            saved.write_bytes(b'preserve me')
            with patch.multiple(app, ROOT=root):
                with self.assertRaisesRegex(RuntimeError, 'Incomplete'):
                    app.ensure_backups('do')
            self.assertEqual(saved.read_bytes(), b'preserve me')


if __name__ == '__main__':
    unittest.main()
