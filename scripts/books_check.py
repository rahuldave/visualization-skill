"""Stop a commit that holds a book. The books are under copyright, so they must never reach Git.

Run it from the root of the repository:

    python -I scripts/books_check.py            # check the files that Git will commit
    python -I scripts/books_check.py --history  # also check every file in the history

It exits with 1 when it finds a book, and with 2 when Git fails.
"""

import subprocess
import sys

BOOK_ENDINGS = (".pdf", ".ps", ".epub", ".mobi", ".azw", ".azw3", ".djvu", ".fb2", ".chm", ".cbz",
                ".zip", ".7z", ".rar", ".tar", ".tgz", ".gz", ".bz2", ".xz", ".zst")
# The first bytes of a PDF, a ZIP (also an EPUB), a gzip, a 7z and a RAR file
MAGIC = (b"PK\x03\x04", b"\x1f\x8b", b"7z\xbc\xaf", b"Rar!")
LARGEST_FILE = 1024 * 1024
SYMLINK_MODE = "120000"
SUBMODULE_MODE = "160000"


def git(*args, stdin=None):
    """Run Git and return its output as bytes. Stop with exit code 2 when Git fails."""
    result = subprocess.run(["git", *args], input=stdin, capture_output=True)
    if result.returncode != 0:
        sys.stderr.write(f"git {' '.join(args)} failed: {result.stderr.decode(errors='replace')}")
        sys.exit(2)
    return result.stdout


def bad_name(path):
    """Return the reason that a path name looks like a book, or None."""
    lower = path.lower()
    if "books" in lower.split("/")[:-1]:
        return "it is in a books folder"
    if lower.endswith(BOOK_ENDINGS):
        return "its name ends like a book or an archive"
    return None


def bad_content(size, head):
    """Return the reason that a file's size or first bytes look like a book, or None."""
    if size > LARGEST_FILE:
        return f"it is larger than {LARGEST_FILE} bytes"
    if b"%PDF-" in head[:1024]:
        return "its content is a PDF"
    if head.startswith(MAGIC):
        return "its content is an archive, such as a ZIP or an EPUB"
    return None


def read_blobs(shas):
    """Return {sha: (size, first 1024 bytes)} for each blob, with one call to Git."""
    shas = list(dict.fromkeys(shas))
    if not shas:
        return {}
    out = git("cat-file", "--batch", stdin=("\n".join(shas) + "\n").encode())
    blobs, pos = {}, 0
    for sha in shas:
        end = out.index(b"\n", pos)
        _name, _kind, size = out[pos:end].split()
        size = int(size)
        blobs[sha] = (size, out[end + 1:end + 1 + min(size, 1024)])
        pos = end + 1 + size + 1
    return blobs


def problems_in_index():
    """List each staged file that looks like a book, by its name, its kind or its content."""
    entries = []
    for entry in git("ls-files", "-s", "-z").split(b"\0"):
        if entry:
            info, raw_path = entry.split(b"\t", 1)
            mode, sha, _stage = info.decode().split()
            entries.append((mode, sha, raw_path.decode(errors="replace")))
    blobs = read_blobs(sha for mode, sha, _ in entries if mode not in (SUBMODULE_MODE,))
    found = []
    for mode, sha, path in entries:
        reason = bad_name(path)
        if reason is None and mode == SYMLINK_MODE:
            reason = "it is a symbolic link, which publishes a local path"
        if reason is None and mode == SUBMODULE_MODE:
            reason = "it is a submodule, which this check cannot read"
        if reason is None:
            reason = bad_content(*blobs[sha])
        if reason:
            found.append(f"{path}: {reason}")
    return found


def problems_in_history():
    """List each file in the whole history that looks like a book, by its name or its content."""
    paths = {}
    for line in git("rev-list", "--objects", "--all").decode(errors="replace").splitlines():
        sha, _, path = line.partition(" ")
        paths.setdefault(sha, path)
    if not paths:
        return []
    kinds = git("cat-file", "--batch-check=%(objectname) %(objecttype)",
                stdin=("\n".join(paths) + "\n").encode()).decode().split("\n")
    blob_shas = [line.split()[0] for line in kinds if line.endswith(" blob")]
    blobs = read_blobs(blob_shas)
    found = set()
    for sha in blob_shas:
        reason = bad_name(paths[sha]) or bad_content(*blobs[sha])
        if reason:
            found.add(f"{paths[sha] or sha}: {reason}, in the history")
    return sorted(found)


def main(argv):
    found = problems_in_index()
    if "--history" in argv:
        found += problems_in_history()
    for line in found:
        print(line, file=sys.stderr)
    if found:
        print("A book may be in Git. Remove it, and keep the books in the ignored folder books/.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
