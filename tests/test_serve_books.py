"""Tests for scripts/serve_books.sh and scripts/serve_site.py, the server that shows books/ on a phone.

Each test copies the scripts into a temporary folder with a made-up books/ and serves it on 127.0.0.1.
The tests need pandoc and are skipped without it.
"""

import os
import pathlib
import shutil
import signal
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
SUMMARY = "schwabish-dataviz-summary"


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for(test, timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        if test():
            return True
        time.sleep(0.2)
    return False


needs_pandoc = unittest.skipUnless(shutil.which("pandoc"), "pandoc is not installed")


class Server(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        shutil.copytree(ROOT / "scripts", self.root / "scripts")
        self.books = self.root / "books"
        (self.books / "figures").mkdir(parents=True)
        (self.books / "figures" / "p001-1.png").write_bytes(b"\x89PNG\r\n")
        (self.books / "book.pdf").write_bytes(b"%PDF secret")
        self.page(SUMMARY, "# Summary\n\nSee [one](one.md).\n")
        self.page("one", "# One\n\nBack to the [summary](schwabish-dataviz-summary.md).\n")
        self.port = free_port()
        self.procs = []

    def tearDown(self):
        for proc in self.procs:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.communicate()
        self.tmp.cleanup()

    def page(self, name, text):
        (self.books / f"{name}.md").write_text(text)

    def start(self, command=None, env=None):
        env = {**os.environ, "SERVE_BOOKS_IP": "127.0.0.1", **(env or {})}
        command = command or ["bash", str(self.root / "scripts" / "serve_books.sh"), str(self.port)]
        proc = subprocess.Popen(command, env=env, start_new_session=True, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.procs.append(proc)
        return proc

    def get(self, path):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/{path}", timeout=2) as reply:
                return reply.status, reply.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as error:
            error.close()
            return error.code, ""
        except (urllib.error.URLError, ConnectionError, socket.timeout):
            return None, ""

    def serve(self):
        proc = self.start()
        self.assertTrue(wait_for(lambda: self.get("")[0] == 200), "the server did not start")
        return proc

    def site(self, name):
        return self.books / "site" / name


@needs_pandoc
class Pages(Server):
    def test_pages_and_figures_are_served(self):
        self.serve()
        status, body = self.get("")
        self.assertIn('href="one.html"', body)
        self.assertEqual(self.get("one.html")[0], 200)
        self.assertEqual(self.get("figures/p001-1.png")[0], 200)

    def test_links_between_pages_are_rewritten(self):
        self.page("links", "\n".join([
            "[a](one.md) [b](one.md#part) [c](./one.md) [d](https://example.com/r.md)",
            "[e](../README.md)", "", "    <a href=\"one.md\">code</a>", ""]))
        self.serve()
        self.assertTrue(wait_for(lambda: self.site("links.html").exists()))
        body = self.site("links.html").read_text()
        self.assertEqual(body.count('href="one.html"'), 2)
        self.assertIn('href="one.html#part"', body)
        self.assertIn('href="https://example.com/r.md"', body)
        self.assertIn('href="../README.md"', body)
        self.assertIn("one.md", body.split("<pre")[1])  # code is left alone


@needs_pandoc
class OnlyThePages(Server):
    """The server shows HTML pages and PNG figures, and nothing else."""

    def test_pdf_is_never_served(self):
        shutil.copy(self.books / "book.pdf", self.books / "figures" / "book.pdf")
        self.serve()
        shutil.copy(self.books / "book.pdf", self.site("book.pdf"))
        os.symlink("../book.pdf", self.site("link.png"))
        os.symlink(self.books / "book.pdf", self.books / "figures" / "link.png")
        for path in ("book.pdf", "../book.pdf", "figures/../book.pdf", "%2e%2e/book.pdf", "figures/book.pdf",
                     "link.png", "figures/link.png", "/" + str(self.books / "book.pdf")):
            with self.subTest(path=path):
                status, body = self.get(path)
                self.assertEqual(status, 404)
                self.assertNotIn("secret", body)

    def test_folders_are_not_listed(self):
        self.serve()
        self.assertEqual(self.get("figures/")[0], 404)


@needs_pandoc
class Robust(Server):
    def test_caller_survives_a_stop(self):
        """Stopping the script stops its children only, not the shell that started it."""
        script = self.root / "scripts" / "serve_books.sh"
        pidfile = self.root / "pid"
        wrapper = f'bash "{script}" {self.port} & echo $! > "{pidfile}"; wait; echo survived'
        proc = self.start(["bash", "-c", wrapper])
        self.assertTrue(wait_for(lambda: self.get("")[0] == 200))
        os.kill(int(pidfile.read_text()), signal.SIGTERM)
        out, _ = proc.communicate(timeout=10)
        self.assertIn("survived", out)
        self.assertEqual(proc.returncode, 0)
        time.sleep(0.5)
        with self.assertRaises(ProcessLookupError):
            os.killpg(proc.pid, 0)  # no process is left behind

    def test_a_bad_page_does_not_stop_the_rebuilds(self):
        self.start(env={"PATH": f"{self.stub_pandoc()}:{os.environ['PATH']}"})
        self.assertTrue(wait_for(lambda: self.get("")[0] == 200))
        self.page("bad", "# Bad\n")
        time.sleep(4)
        self.page("new", "# New\n")
        self.assertTrue(wait_for(lambda: self.site("new.html").exists()), "the loop stopped")

    def test_pages_of_deleted_markdown_are_removed(self):
        self.serve()
        (self.books / "one.md").unlink()
        self.assertTrue(wait_for(lambda: not self.site("one.html").exists()))
        self.assertEqual(self.get("one.html")[0], 404)

    def test_restart_with_a_dangling_figures_link(self):
        shutil.rmtree(self.books / "figures")
        first = self.serve()
        os.killpg(first.pid, signal.SIGTERM)
        first.wait(timeout=10)
        self.assertTrue(self.site("figures").is_symlink())
        self.serve()

    def test_no_pages_fails_plainly(self):
        for md in self.books.glob("*.md"):
            md.unlink()
        proc = self.start()
        _, err = proc.communicate(timeout=10)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("no Markdown pages", err)

    def test_figures_made_after_the_start_are_served(self):
        shutil.rmtree(self.books / "figures")
        self.serve()
        (self.books / "figures").mkdir()
        (self.books / "figures" / "late.png").write_bytes(b"\x89PNG\r\n")
        self.assertEqual(self.get("figures/late.png")[0], 200)

    def test_a_failed_page_is_reported_once(self):
        self.page("bad", "# Bad\n")
        proc = self.start(env={"PATH": f"{self.stub_pandoc()}:{os.environ['PATH']}"})
        self.assertTrue(wait_for(lambda: self.get("")[0] == 200))
        time.sleep(7)
        os.killpg(proc.pid, signal.SIGTERM)
        _, err = proc.communicate(timeout=10)
        self.assertEqual(err.count("could not convert bad.md"), 1)

    def test_a_page_named_index_does_not_hide_the_summary(self):
        self.page("index", "# Not the contents\n")
        self.serve()
        time.sleep(4)
        self.assertIn("Summary", self.get("")[1])
        self.assertNotIn("Not the contents", self.get("")[1])

    def stub_pandoc(self):
        """A pandoc that fails on bad.md and runs the real one on every other page."""
        stub = self.root / "stub"
        stub.mkdir()
        (stub / "pandoc").write_text(
            f'#!/bin/sh\ncase "$1" in *bad.md) exit 1 ;; esac\nexec "{shutil.which("pandoc")}" "$@"\n')
        (stub / "pandoc").chmod(0o755)
        return stub


class NoTailscale(Server):
    def test_missing_tailscale_says_so(self):
        bin = self.root / "bin"
        bin.mkdir()
        for tool in ("bash", "dirname", "basename"):
            os.symlink(shutil.which(tool), bin / tool)
        proc = self.start(env={"SERVE_BOOKS_IP": "", "PATH": str(bin)})
        _, err = proc.communicate(timeout=10)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("tailscale command is not on the PATH", err)

if __name__ == "__main__":
    unittest.main()
