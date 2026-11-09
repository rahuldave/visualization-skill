"""Tests for the prose recipe of the Justfile and for .gitignore. Each test works in a temporary Git repository.

The tests that run check.py download it from GitHub, so they need the network, as `just prose` does.
"""

import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
JUSTFILE = ROOT / "Justfile"
GOOD = "# A page\n\nThe page has one short sentence.\n"
BAD = "# A page\n\nThis is a bad page — with a dash.\n"


class Repository(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.git("init", "-q")
        shutil.copy(ROOT / ".gitignore", self.root / ".gitignore")

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], capture_output=True, text=True)

    def page(self, name, text, track=True):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        if track:
            self.git("add", "-f", name)

    def prose(self, *args):
        return subprocess.run(["just", "-f", str(JUSTFILE), "-d", str(self.root), "prose", *args],
                              capture_output=True, text=True)


class ProseArguments(Repository):
    """The recipe rejects a bad argument with one plain line, before it downloads anything."""

    def test_unknown_option_fails_plainly(self):
        for option in ("-h", "--bogus", "-", "--"):
            with self.subTest(option=option):
                result = self.prose(option)
                self.assertEqual(result.returncode, 2)
                self.assertIn("unknown option", result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_missing_file_fails_plainly(self):
        for name in ("nope.md", ""):
            with self.subTest(name=name):
                result = self.prose(name)
                self.assertEqual(result.returncode, 2)
                self.assertIn("no such file", result.stderr)
                self.assertNotIn("Traceback", result.stderr)


class ProsePages(Repository):
    """With no page named, the recipe checks every Markdown page in Git, also when -v is given."""

    def test_default_checks_every_tracked_page(self):
        self.page("README.md", GOOD)
        self.page("docs/later.md", BAD)
        result = self.prose()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("docs/later.md", result.stdout)

    def test_verbose_alone_still_checks_the_pages(self):
        self.page("README.md", BAD)
        self.assertEqual(self.prose("-v").returncode, 1)

    def test_untracked_page_is_not_checked(self):
        self.page("README.md", GOOD)
        self.page("draft.md", BAD, track=False)
        self.assertEqual(self.prose().returncode, 0)

    def test_named_page_with_space_is_checked(self):
        self.page("README.md", GOOD)
        self.page("my notes.md", BAD, track=False)
        self.assertEqual(self.prose("-v", "my notes.md").returncode, 1)


class Ignore(Repository):
    def ignored(self, path):
        return self.git("check-ignore", "-q", "--no-index", path).returncode == 0

    def test_books_and_finder_files_are_ignored(self):
        for path in ("books/a.pdf", "books/sub/x.md", ".DS_Store", "docs/.DS_Store"):
            with self.subTest(path=path):
                self.assertTrue(self.ignored(path))

    def test_pages_are_not_ignored(self):
        self.assertFalse(self.ignored("README.md"))


class JustfileText(unittest.TestCase):
    def test_justfile_names_no_private_file(self):
        self.assertNotIn("books/", JUSTFILE.read_text())


if __name__ == "__main__":
    unittest.main()
