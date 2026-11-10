#!/usr/bin/env bash
# Serve the Markdown pages of books/ as HTML, to this machine's tailnet only.
# usage: serve_books.sh [PORT]
# The pages are converted with pandoc into books/site/, which holds only HTML and a link to the figures.
# serve_site.py serves only .html and .png files from there, so the book's PDF is never served.
# A page is converted again when its Markdown or this script changes, and removed when its Markdown is gone.
# SERVE_BOOKS_IP sets the address to listen on in place of the tailnet address. The tests use it.
set -euo pipefail
shopt -s nullglob
port="${1:-8765}"
here="$(cd "$(dirname "$0")" && pwd)"
script="$here/$(basename "$0")"
src="$(dirname "$here")/books"
out="$src/site"
python="${SERVE_BOOKS_PYTHON:-python3}"

if [ -n "${SERVE_BOOKS_IP:-}" ]; then
    ip="$SERVE_BOOKS_IP"
else
    command -v tailscale >/dev/null || { echo "serve_books: the tailscale command is not on the PATH." >&2; exit 1; }
    ip="$(tailscale ip -4 2>/dev/null | head -1)" || true
    [ -n "$ip" ] || { echo "serve_books: this machine has no tailnet address. Start Tailscale first." >&2; exit 1; }
fi
command -v pandoc >/dev/null || { echo "serve_books: pandoc is not installed." >&2; exit 1; }
pages=("$src"/*.md)
[ "${#pages[@]}" -gt 0 ] || { echo "serve_books: no Markdown pages in $src." >&2; exit 1; }
mkdir -p "$out"
ln -sfn ../figures "$out/figures"

css='<style>
body{max-width:46em;margin:0 auto;padding:1em 16px 4em;font:17px/1.55 -apple-system,system-ui,sans-serif;color:#222;background:#fff}
img{max-width:100%;height:auto;border:1px solid #ddd}
a{color:#0b5cad}a:visited{color:#6b3fa0}
code{font-size:.9em}
table{border-collapse:collapse;display:block;overflow-x:auto}
td,th{border:1px solid #ccc;padding:.3em .5em}
nav{font-size:.9em;margin-bottom:1em}
@media (prefers-color-scheme:dark){body{color:#ddd;background:#161616}a{color:#7ab8ff}a:visited{color:#c8a2ff}img{background:#fff}}
</style>'
header="$(mktemp)"
loop="" server=""
# Stop only our own children, never the caller. The loop's sleep or pandoc goes too
trap 'rm -f -- "$header"; [ -n "$loop" ] && pkill -P "$loop" 2>/dev/null; kill $loop $server 2>/dev/null || true' EXIT
trap 'exit 130' INT TERM
printf '%s\n<nav><a href="index.html">Contents</a></nav>\n' "$css" > "$header"

build() {
    local md name html
    for md in "$src"/*.md; do
        name="$(basename "$md" .md)"
        [ "$name" = index ] && continue  # the summary's copy is index.html
        html="$out/$name.html"
        if [ "$html" -nt "$md" ] && [ "$html" -nt "$script" ]; then continue; fi
        # A page that failed is tried again only when it changes. Its last text is kept to compare, because
        # file times count only whole seconds here
        if cmp -s "$md" "$html.failed" && [ "$html.failed" -nt "$script" ]; then continue; fi
        if ! pandoc "$md" -f gfm -t html5 -s -V pagetitle="$name" \
            --include-before-body="$header" -o "$html.tmp"; then
            echo "serve_books: could not convert $name.md" >&2
            rm -f "$html.tmp"
            cp "$md" "$html.failed"
            continue
        fi
        # Links between the pages point to the HTML copies
        sed -E 's/href="(\.\/)?([^"/:?]+)\.md(#[^"]*)?"/href="\2.html\3"/g' "$html.tmp" > "$html.new"
        rm -f "$html.tmp" "$html.failed"
        mv -f "$html.new" "$html"
        echo "built $name.html"
    done
    # Remove the pages whose Markdown is gone
    for html in "$out"/*.html; do
        name="$(basename "$html" .html)"
        [ "$name" = index ] && continue
        [ -f "$src/$name.md" ] || { rm -f "$html" "$html.failed"; echo "removed $name.html"; }
    done
    if [ -f "$out/schwabish-dataviz-summary.html" ]; then
        cp -p "$out/schwabish-dataviz-summary.html" "$out/index.html.new"
        mv -f "$out/index.html.new" "$out/index.html"
    else
        rm -f "$out/index.html"
    fi
}

build
( while sleep 3; do build || true; done ) &
loop=$!
"$python" -I "$here/serve_site.py" "$out" "$ip" "$port" &
server=$!
wait $server
