# visualization-skill: every task is a recipe here. `just` lists them.

# Each word after a recipe's name reaches its commands whole, as "$1", "$2" and so on; "$@" is all of them
set positional-arguments

# Python comes from uv. The recipes also need bash, curl, and access to GitHub for check.py
python := "uv run --no-project --quiet python"

# The checker for prose, check.py of nossaifd, at a fixed commit of its main branch. Move it when
# check.py changes there.
nossaifd_commit := "ec80717f074c68dfa5fecb0c8c19ba49398a2f76"

[private]
default:
    @just --list --unsorted

# Check Markdown pages with check.py of nossaifd: every page in Git, or the pages you name. -v shows the soft notes
prose *args:
    #!/usr/bin/env bash
    set -euo pipefail
    flags=() pages=()
    for word in "$@"; do
        case "$word" in
            -v) flags+=("-v") ;;
            -*) echo "just prose: unknown option '$word'. The only option is -v." >&2; exit 2 ;;
            *) [ -f "$word" ] || { echo "just prose: no such file: '$word'" >&2; exit 2; }; pages+=("$word") ;;
        esac
    done
    if [ "${#pages[@]}" -eq 0 ]; then
        while IFS= read -r -d '' page; do pages+=("$page"); done < <(git ls-files -z '*.md')
    fi
    tool_root="$(mktemp -d)"
    trap 'rm -rf -- "$tool_root"' EXIT
    curl -fsSL "https://raw.githubusercontent.com/rahuldave/nossaifd/{{nossaifd_commit}}/check.py" -o "$tool_root/check.py"
    {{python}} -I "$tool_root/check.py" ${flags[@]+"${flags[@]}"} "${pages[@]}"

# Check that no book is in Git, because the books are under copyright. Add --history to check every name in the history
books-check *args:
    {{python}} -I scripts/books_check.py "$@"

# Run the tests. Extra arguments go to unittest
test *args:
    {{python}} -I -m unittest discover -s tests -q "$@"

# Install a pre-commit hook in this clone, which runs the books check before each commit
hooks:
    #!/usr/bin/env bash
    set -euo pipefail
    hook="$(git rev-parse --git-path hooks)/pre-commit"
    marker="# visualization-skill books check"
    if [ -e "$hook" ] && ! grep -qF "$marker" "$hook"; then
        echo "$hook exists and is not ours. Add 'just books-check' to it by hand." >&2
        exit 1
    fi
    printf '#!/bin/sh\n%s\nif ! command -v just >/dev/null 2>&1; then\n  echo "The books check needs just on the PATH." >&2\n  exit 1\nfi\nexec just books-check\n' "$marker" > "$hook"
    chmod +x "$hook"
    echo "Installed $hook"

# Everything a commit must pass
check:
    just books-check --history
    just test
    just prose
