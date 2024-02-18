"""
Testing `uptpy`. What to test:
* delete files that are already deleted.
* create folders in subfolders (making dir tree needs to work)
* simple file change
* add and delete files
* delete directory tree
* nothing-to-to
* ignoring uptpy-unknown remote files
* special characters in file and dir names
"""

import os
import sys
import json
import uuid
import shutil
import unittest
import posixpath

THIS_DIR = os.path.abspath(os.path.dirname(__file__))
TEST_DIR = os.path.join(THIS_DIR, 'local')
CREDS_NAME = '_ test_creds.json'
CREDS_FILE = os.path.join(THIS_DIR, CREDS_NAME)
ERR_NEED_CREDS = 'Need credentials in file %s to perform tests!' % CREDS_FILE


if __name__ == '__main__':
    parent_path = os.path.dirname(THIS_DIR)
    if parent_path not in sys.path:
        sys.path.append(parent_path)
import uptpy  # noqa: E402


class Test(unittest.TestCase):
    def __init__(self, args):
        super(Test, self).__init__(args)
        if not os.path.isfile(CREDS_FILE):
            self.skipTest(ERR_NEED_CREDS)
            return

        try:
            with open(CREDS_FILE, encoding='utf8') as file_obj:
                self.creds = json.load(file_obj)
        except json.JSONDecodeError as error:
            raise RuntimeError(
                'Could not load test credentials from "%s"!\n %s' % (CREDS_NAME, error)
            )

        self._rp = self.creds['remote_path']
        self._usr = self.creds['user']
        self._pw = self.creds['passwd']
        self._hst = self.creds['host']
        self._test_creds = (self._hst, self._usr, self._pw)
        self._test_connection = (self._hst, self._usr, self._pw, TEST_DIR, self._rp)

    def test_manitest(self):
        # self.skipTest('')
        ftp = uptpy.get_ftp(*self._test_creds)[0]
        current = uptpy.load_manifest(ftp, self._rp)

        remote = uptpy.scan_remote(ftp, self._rp)
        self.assertTrue(isinstance(remote, dict))
        self.assertTrue('' in remote)
        self.assertTrue('data.json' in remote[''])
        self.assertTrue('size' in remote['']['data.json'])

        self._ensure_deleted(ftp, self._rp, uptpy.REMOTE_MANIFEST)
        self.assertEqual(uptpy.load_manifest(ftp, self._rp), {})

        uptpy.update_manifest(ftp, current, TEST_DIR, self._rp)
        ftp.close()

    def test_delete(self):
        # self.skipTest('')
        name = 'delete.me'
        # prepare
        ftp = uptpy.get_ftp(*self._test_creds)[0]
        self._ensure_deleted(ftp, self._rp, name)

        new_file = os.path.join(TEST_DIR, name)
        with open(new_file, 'w', encoding='utf8') as fobj:
            fobj.write('1337')

        # sync
        uptpy.update(*self._test_connection)
        # delete remotely
        self._ensure_deleted(ftp, self._rp, name)
        # delete locally
        os.unlink(new_file)
        # re-sync (file is in manifest and should be tried to delete)
        num_changes = uptpy.update(*self._test_connection)
        self.assertEqual(num_changes, 0)

        ftp.close()

    def test_dirtree_add_create(self):
        # self.skipTest('')
        prefix = '_random_'
        # remove old random dir locally
        for item in os.scandir(TEST_DIR):
            if item.is_dir() and item.name.startswith(prefix):
                shutil.rmtree(item.path)

        # create new local random dir
        dirname = prefix + str(uuid.uuid4())
        dirpath = os.path.join(TEST_DIR, dirname)
        os.mkdir(dirpath)
        subdir = os.path.join(dirpath, 'subdir')
        os.mkdir(subdir)
        subdir2 = os.path.join(subdir, 'subdir2')
        os.mkdir(subdir2)
        for i in range(3):
            subfile = os.path.join(subdir, 'file%i.txt' % i)
            with open(subfile, 'w', encoding='utf8') as fobj:
                fobj.write('chuckles')
            subfile2 = os.path.join(subdir2, 'file%i.bin' % i)
            with open(subfile2, 'wb') as fobj:
                fobj.write(b'\x00\x00\x00')

        num_changes = uptpy.update(*self._test_connection)

        ftp = uptpy.get_ftp(*self._test_creds)[0]
        rthings = sorted(
            os.path.relpath(i, self._rp) for i in ftp.nlst(self._rp) if not i.endswith('.')
        )
        ftp.close()
        # lthings = sorted(i.name for i in os.scandir(TEST_DIR))
        self.assertTrue(dirname in rthings)
        self.assertEqual(len([i for i in rthings if i.startswith(prefix)]), 1)
        self.assertNotEqual(num_changes, 0)

    def test_change(self):
        data_json = os.path.join(TEST_DIR, 'data.json')
        if not os.path.isfile(data_json):
            local_data = {'nothing': None}
        else:
            with open(data_json, encoding='utf8') as fobj:
                local_data = json.load(fobj)
        local_data['random'] = str(uuid.uuid4()) # type: ignore
        with open(data_json, 'w', encoding='utf8') as fobj:
            json.dump(local_data, fobj)

        ftp = uptpy.get_ftp(*self._test_creds)[0]
        uptpy.mkdirs(ftp, self._rp, '')

        def _get_remote_data():
            try:
                content = uptpy.read_remote(ftp, posixpath.join(self._rp, 'data.json'))
                return json.loads(content)
            except Exception:
                return {}

        remote_data1 = _get_remote_data()

        result = uptpy.update(*self._test_connection)
        self.assertTrue(result > 0)

        remote_data2 = _get_remote_data()
        ftp.close()

        self.assertNotEqual(remote_data1.get('random'), remote_data2['random'])
        self.assertEqual(local_data['random'], remote_data2['random'])

    def test_non_ascii_names(self):
        # might be this was a problem when I initially wrote it with Python2?
        # This all works out of the box now. Nice :)
        smiley = '_\ud83e\udd17'.encode('utf-16', 'surrogatepass').decode('utf-16')
        file_name = '_Str\u00ebu\u00dfel%sbr\u00f6tchen.txt' % smiley
        rel_path = posixpath.join(smiley, file_name)
        file_path = os.path.join(TEST_DIR, rel_path)
        content = _make_file(file_path)

        ftp = uptpy.get_ftp(*self._test_creds)[0]
        uptpy.update(*self._test_connection, in_ftp=ftp)

        remote_content = uptpy.read_remote(ftp, posixpath.join(self._rp, rel_path))
        self.assertEqual(remote_content, content)

    def test_ignored_remotely(self):
        rel_path1 = 'DO_BE_IGNORED.nop'
        rel_path2 = posixpath.join('IGNORE_SUBDIR', 'DO_BE_IGNORED.nop')
        local_file1 = os.path.join(TEST_DIR, rel_path1)
        local_file2 = os.path.join(TEST_DIR, rel_path2)
        for path in local_file1, local_file2:
            if os.path.isfile(path):
                os.unlink(path)
            self.assertFalse(os.path.isfile(path))

        ftp = uptpy.get_ftp(*self._test_creds)[0]
        uptpy.update(*self._test_connection, in_ftp=ftp)

        content1 = _make_file(local_file1)
        content2 = _make_file(local_file2)

        uptpy._upload(ftp, rel_path1, TEST_DIR, self._rp)
        uptpy.mkdirs(ftp, self._rp, 'IGNORE_SUBDIR')
        uptpy._upload(ftp, rel_path2, TEST_DIR, self._rp)

        for path in local_file1, local_file2:
            os.unlink(path)
            self.assertFalse(os.path.isfile(path))

        result = uptpy.update(*self._test_connection, in_ftp=ftp)
        self.assertEqual(result, 0)

        for rel_path, content in ((rel_path1, content1), (rel_path2, content2)):
            remote_content = uptpy.read_remote(ftp, posixpath.join(self._rp, rel_path))
            self.assertEqual(remote_content, content)

    def _ensure_deleted(self, ftp, remote_root, name):
        remote_path = posixpath.join(remote_root, name)
        uptpy.mkdirs(ftp, remote_root)
        things = ftp.nlst(remote_root)
        if remote_path in things:
            ftp.delete(remote_path)
            things = ftp.nlst(remote_root)
            self.assertFalse(remote_path in things)


def _make_file(file_path, content=None):
    if os.path.isfile(file_path):
        with open(file_path, encoding='utf8') as fobj:
            return fobj.read()
    dir_path = os.path.dirname(file_path)
    if not os.path.isdir(dir_path):
        os.makedirs(dir_path)
    if content is None:
        content = str(uuid.uuid4())
    with open(file_path, 'w', encoding='utf8') as fobj:
        fobj.write(content)
    return content


if __name__ == '__main__':
    unittest.main(verbosity=2)
