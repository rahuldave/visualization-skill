"""Serve the HTML pages and figures of books/site, and nothing else.

usage: serve_site.py SITE_DIR ADDRESS PORT
Only .html and .png files are served. A path whose real location is outside SITE_DIR and the folder its
figures link points to gets 404, and no folder is listed.
"""
import functools, http.server, os, sys

SUFFIXES = (".html", ".png")


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, roots, **kwargs):
        self.roots = roots
        super().__init__(*args, **kwargs)

    def send_head(self):
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            path = os.path.join(path, "index.html")
        real = os.path.realpath(path)
        inside = any(real.startswith(root + os.sep) for root in self.roots)
        if not (inside and real.endswith(SUFFIXES) and os.path.isfile(real)):
            self.send_error(404, "File not found")
            return None
        return super().send_head()

    def list_directory(self, path):
        self.send_error(404, "File not found")
        return None


def main(site, address, port):
    site = os.path.realpath(site)
    # The figures may appear after the server starts, so their root is added either way
    roots = [site, os.path.realpath(os.path.join(site, "figures"))]
    handler = functools.partial(Handler, directory=site, roots=roots)
    with http.server.ThreadingHTTPServer((address, int(port)), handler) as server:
        print(f"Serving on http://{address}:{port}/", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main(*sys.argv[1:4])
