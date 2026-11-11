"""helpers/path.py: public-file storage rooted at cwd/PUBLIC_FOLDER (a temp dir here)."""
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from helpers import path as storage
from globals import IMAGE_TYPE_GALLERY, IMAGE_TYPE_LOGOS, IMAGES_FOLDER, PAGES_FOLDER

LOCAL = 'local-1'


class StorageTestCase(unittest.TestCase):
    """Runs from a throw-away cwd with PUBLIC_FOLDER=public, so nothing touches the real public/ folder."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = os.path.realpath(tmp.name)
        previous = os.getcwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, previous)
        os.mkdir('public')
        patcher = mock.patch.dict(os.environ, {'PUBLIC_FOLDER': 'public'})
        patcher.start()
        self.addCleanup(patcher.stop)

    def local_path(self, *parts):
        return os.path.join(self.root, 'public', LOCAL, *parts)


class FakeUpload:
    def __init__(self, content=b'data'):
        self.content = content

    def save(self, destination):
        with open(destination, 'wb') as f:
            f.write(self.content)


class TestAllowedFile(unittest.TestCase):

    def test_allowed_extensions(self):
        for name in ('a.png', 'a.jpg', 'a.jpeg', 'page.html', 'sitemap.xml'):
            with self.subTest(name=name):
                self.assertTrue(storage.allowed_file(name))

    def test_extension_check_ignores_case(self):
        self.assertTrue(storage.allowed_file('PHOTO.JPG'))

    def test_uses_the_last_extension(self):
        self.assertTrue(storage.allowed_file('archive.tar.png'))
        self.assertFalse(storage.allowed_file('photo.png.php'))

    def test_rejects_other_extensions(self):
        for name in ('malware.exe', 'script.php', 'notes.txt', 'image.svg'):
            with self.subTest(name=name):
                self.assertFalse(storage.allowed_file(name))

    def test_rejects_names_without_extension(self):
        self.assertFalse(storage.allowed_file('png'))
        self.assertFalse(storage.allowed_file(''))


class TestPathBuilders(unittest.TestCase):

    def test_image_path_uses_forward_slashes(self):
        self.assertEqual(storage.generateImagePath('a.png', IMAGE_TYPE_LOGOS), f'{IMAGES_FOLDER}/{IMAGE_TYPE_LOGOS}/a.png')

    def test_gallery_image_path(self):
        self.assertEqual(storage.generateImagePath('a.png', IMAGE_TYPE_GALLERY), f'{IMAGES_FOLDER}/{IMAGE_TYPE_GALLERY}/a.png')

    def test_page_path(self):
        self.assertEqual(storage.generatePagePath('email_confirmed.html'), f'{PAGES_FOLDER}/email_confirmed.html')


class TestCreatePaths(StorageTestCase):

    def test_check_and_create_path_builds_nested_folders_under_cwd(self):
        created = storage.checkAndCreatePath('public', 'a', 'b')

        self.assertEqual(created, os.path.join(self.root, 'public', 'a', 'b'))
        self.assertTrue(os.path.isdir(created))

    def test_check_and_create_path_is_idempotent(self):
        storage.checkAndCreatePath('public', 'a')

        self.assertTrue(os.path.isdir(storage.checkAndCreatePath('public', 'a')))

    def test_create_path_from_local_builds_the_three_folders(self):
        storage.createPathFromLocal(LOCAL)

        self.assertTrue(os.path.isdir(self.local_path(IMAGES_FOLDER, IMAGE_TYPE_LOGOS)))
        self.assertTrue(os.path.isdir(self.local_path(IMAGES_FOLDER, IMAGE_TYPE_GALLERY)))
        self.assertTrue(os.path.isdir(self.local_path(PAGES_FOLDER)))

    def test_create_path_from_local_twice_is_harmless(self):
        storage.createPathFromLocal(LOCAL)
        storage.createPathFromLocal(LOCAL)

        self.assertTrue(os.path.isdir(self.local_path(PAGES_FOLDER)))

    def test_two_locals_get_separate_folders(self):
        storage.createPathFromLocal('local-1')
        storage.createPathFromLocal('local-2')

        self.assertEqual(sorted(os.listdir('public')), ['local-1', 'local-2'])


class TestFiles(StorageTestCase):

    def setUp(self):
        super().setUp()
        storage.createPathFromLocal(LOCAL)
        self.page = f'{PAGES_FOLDER}/email.html'

    def test_save_then_read_back(self):
        storage.saveFile(FakeUpload(b'<html/>'), self.page, LOCAL)

        self.assertEqual(storage.getFile(LOCAL, self.page), b'<html/>')

    def test_saved_file_lands_inside_the_local_folder(self):
        storage.saveFile(FakeUpload(), self.page, LOCAL)

        self.assertTrue(os.path.isfile(self.local_path(PAGES_FOLDER, 'email.html')))

    def test_saving_over_an_existing_file_is_refused(self):
        storage.saveFile(FakeUpload(b'old'), self.page, LOCAL)

        with self.assertRaises(FileExistsError):
            storage.saveFile(FakeUpload(b'new'), self.page, LOCAL)

        self.assertEqual(storage.getFile(LOCAL, self.page), b'old')

    def test_saving_over_an_existing_file_can_be_allowed(self):
        storage.saveFile(FakeUpload(b'old'), self.page, LOCAL)

        storage.saveFile(FakeUpload(b'new'), self.page, LOCAL, update_if_conflict=True)

        self.assertEqual(storage.getFile(LOCAL, self.page), b'new')

    def test_remove_file(self):
        storage.saveFile(FakeUpload(), self.page, LOCAL)

        storage.removeFile(LOCAL, self.page)

        self.assertFalse(os.path.exists(self.local_path(PAGES_FOLDER, 'email.html')))

    def test_removing_a_missing_file_fails(self):
        with self.assertRaises(FileNotFoundError):
            storage.removeFile(LOCAL, self.page)

    def test_reading_a_missing_file_fails(self):
        with self.assertRaises(FileNotFoundError):
            storage.getFile(LOCAL, self.page)

    def test_files_of_one_local_are_not_visible_to_another(self):
        storage.saveFile(FakeUpload(), self.page, LOCAL)
        storage.createPathFromLocal('local-2')

        with self.assertRaises(FileNotFoundError):
            storage.getFile('local-2', self.page)

    def test_remove_path_deletes_the_whole_local_folder_and_only_that_one(self):
        storage.createPathFromLocal('local-2')
        storage.saveFile(FakeUpload(), self.page, LOCAL)

        removed = storage.removePath(LOCAL)

        self.assertEqual(removed, self.local_path())
        self.assertFalse(os.path.exists(self.local_path()))
        self.assertTrue(os.path.isdir(os.path.join(self.root, 'public', 'local-2')))

    def test_files_are_stored_as_given_without_text_conversion(self):
        payload = bytes(range(256))
        storage.saveFile(FakeUpload(payload), f'{IMAGES_FOLDER}/{IMAGE_TYPE_LOGOS}/logo.png', LOCAL)

        self.assertEqual(storage.getFile(LOCAL, f'{IMAGES_FOLDER}/{IMAGE_TYPE_LOGOS}/logo.png'), payload)


if __name__ == '__main__':
    unittest.main()
