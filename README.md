# visualization-skill

**An agent skill for charts and data figures.** An agent skill is a folder of instructions that an AI agent
loads before it does a kind of task. This skill will tell an agent how to choose a chart, how to draw it and
how to check it. It covers charts and data figures in papers, reports, web pages and talks. It does not cover
the look of slides, which is the work of [look-talks](https://github.com/rahuldave/look-talks).

The project is new, and it holds no skill yet. The first step is a summary of Jonathan Schwabish's book
*Better Data Visualizations* (Columbia University Press, 2021). The skill will take its rules from that
summary and from other sources. Each rule will name its source and the pages of the book.

## Check the files

The checks need `just`, `uv`, `bash` and `curl`, and access to GitHub. Run `just` to list the tasks.

- `just check` runs every check that a commit must pass. The CI job on GitHub runs it too.
- `just prose` checks the Markdown files in Git with `check.py` of nossaifd. Add `-v` to see the soft notes.
- `just books-check` makes sure that no book is in Git.
- `just hooks` installs a pre-commit hook in your clone, which runs the books check before each commit.

## The books

The folder `books/` holds copies of the books that the skill uses, and the author's notes on them. Git
ignores the folder. The books are under copyright, so never commit them, publish them or copy long passages
from them. The summary of the book stays in `books/` while the author adds notes to it.

## Related work

- **[nossaifd-talks](https://github.com/rahuldave/nossaifd-talks)** holds the guide for talks. Its rules 66
  to 69 cover figures in a talk, and they leave the detailed advice on charts to this skill.
- **[nossaifd](https://github.com/rahuldave/nossaifd)** holds the writing guide, GUIDE.md, and its
  checker, `check.py`. Every Markdown file in this repository follows that guide.
- **[look-talks](https://github.com/rahuldave/look-talks)** holds the skill for the look of slides. The two
  skills share the books check and the layout of the repository.

## Licence

The code and the text are under the MIT licence. See [LICENSE](LICENSE). The books in `books/` are not part
of the repository, and the licence does not cover them.
