# markdown-footnote-checker-cli

Check Markdown footnotes are complete both ways, fail CI on a gap.

[![CI](https://github.com/haiderstudio/markdown-footnote-checker-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/haiderstudio/markdown-footnote-checker-cli/actions/workflows/ci.yml) [![Licence: MIT](https://img.shields.io/badge/Licence-MIT-yellow.svg)](LICENSE)

## What it does

`markdown_footnote_checker` reads each Markdown file,
finds its footnotes, and checks they are complete both
ways:

- A footnote reference with no definition renders as
  literal `[^1]` text in the reader's face, and an
  orphan definition sits at the bottom of the doc
  pointing at nothing. Docs writers renumber and delete
  footnotes by hand all the time. This tool reports every
  dangling reference and orphan definition with its file
  and line number, and exits 1 when any problem is found
  — so it can fail a CI run. A clean file exits 0.
- Every reference `[^label]` in the text must have a
  matching definition `[^label]: ...`, and every
  definition must actually be referenced. A reference
  with no definition is one problem; a definition nobody
  references is one problem.
- A label defined twice is one problem, reported at the
  second definition.
- Labels match without regard to case, so `[^Note]`
  matches `[^note]: ...`. A reference may come before or
  after its definition; order does not matter.
- A definition's own text can reference another
  footnote, and that reference counts — a definition can
  point at another footnote.
- Footnotes inside fenced code blocks (``` or ~~~) are
  skipped — they are examples, not footnotes. Footnotes
  inside inline code spans (`` `[^1]` ``) are skipped
  too — they are code, not footnotes.
- Files come from the command line (one or more), or from
  a folder walk: every `.md` and `.markdown` file under a
  folder, recursively by default (`--no-recursive` stops
  at the top level). `.git` folders are never walked, and
  directory links are never followed, so a link cycle
  cannot loop the check.
- `--exclude PATTERN` skips files by glob, for example
  `--exclude 'sub/nested.md'`. It can be repeated. A file
  passed directly on the command line is always checked,
  even if it matches an exclude pattern and even if it
  has no Markdown extension.
- `--stdin` reads one Markdown file from standard input.
- `--json` prints the result as machine-readable JSON (the
  summary goes to standard error, so standard output stays
  clean JSON).
- It is report-only and runs fully offline: it never
  rewrites a file, sends nothing anywhere, and needs no
  API key. Python standard library only.

## What it does NOT do

- It does not rewrite or tidy a Markdown file. A broken
  footnote is reported; fixing it is your job.
- It does not check links, headings, tables, or anything
  else in a Markdown file. This tool's one job is
  footnote completeness.
- It does not skip indented code blocks: only fenced
  code blocks and inline code spans are skipped. A
  footnote-looking line indented by four spaces is
  treated as text.
- It does not fetch anything from a live site. Every input
  is a local file or standard input.

## Who it is for

Every docs writer: a blogger adding a CI step that fails
the build when a footnote points nowhere, or anyone
tidying a README before a release. A dangling footnote is
invisible in the file itself — this catches it before a
reader sees literal `[^1]` in the text.

## How this differs from similar tools

The exact name `markdown-footnote-checker-cli` matches 0
repositories on GitHub (checked Nov 11, 2026), and the
wider field is empty too: `markdown footnote checker`
matches 0 repositories. No rival checks footnote
completeness. This tool does one job: a Python
standard-library-only CLI that checks Markdown footnotes
are complete both ways, reports each gap with file and
line, and exits 1 for CI — no install beyond Python, no
website, no network.

## Install

Python standard library only — no packages to download. You need
Python 3.8 or newer. Clone the repo and run it in place:

```
git clone https://github.com/haiderstudio/markdown-footnote-checker-cli.git
cd markdown-footnote-checker-cli
python3 src/markdown_footnote_checker.py examples/good.md
```

```
examples/good.md: footnotes OK
OK — 1 file(s) checked, all footnotes are complete.
```

## Usage

Check one clean file:

```
python3 src/markdown_footnote_checker.py examples/good.md
```

```
examples/good.md: footnotes OK
OK — 1 file(s) checked, all footnotes are complete.
```

Check a file with broken footnotes — two dangling
references on one line, one more dangling reference, an
orphan definition, and a duplicate definition:

```
python3 src/markdown_footnote_checker.py examples/bad.md
```

```
FAIL examples/bad.md:3: footnote reference 'missing' has no definition
FAIL examples/bad.md:5: footnote reference 'gone' has no definition
FAIL examples/bad.md:5: footnote reference 'also-gone' has no definition
FAIL examples/bad.md:7: footnote definition 'unused' is never referenced
FAIL examples/bad.md:10: footnote 'twice' is defined more than once
Checked 1 file(s), 5 problem(s) in 1 file(s).
```

A broken footnote inside a code block is skipped:

```
python3 src/markdown_footnote_checker.py examples/fenced.md
```

```
examples/fenced.md: footnotes OK
OK — 1 file(s) checked, all footnotes are complete.
```

Check a whole folder:

```
python3 src/markdown_footnote_checker.py examples/
```

```
FAIL examples/bad.md:3: footnote reference 'missing' has no definition
FAIL examples/bad.md:5: footnote reference 'gone' has no definition
FAIL examples/bad.md:5: footnote reference 'also-gone' has no definition
FAIL examples/bad.md:7: footnote definition 'unused' is never referenced
FAIL examples/bad.md:10: footnote 'twice' is defined more than once
examples/fenced.md: footnotes OK
examples/good.md: footnotes OK
examples/sample-output.md: footnotes OK
FAIL examples/sub/nested.md:3: footnote reference 'lost' has no definition
Checked 5 file(s), 6 problem(s) in 2 file(s).
```

Skip one file with `--exclude`:

```
python3 src/markdown_footnote_checker.py --exclude 'sub/nested.md' examples/
```

```
FAIL examples/bad.md:3: footnote reference 'missing' has no definition
FAIL examples/bad.md:5: footnote reference 'gone' has no definition
FAIL examples/bad.md:5: footnote reference 'also-gone' has no definition
FAIL examples/bad.md:7: footnote definition 'unused' is never referenced
FAIL examples/bad.md:10: footnote 'twice' is defined more than once
examples/fenced.md: footnotes OK
examples/good.md: footnotes OK
examples/sample-output.md: footnotes OK
Checked 4 file(s), 5 problem(s) in 1 file(s).
```

Check one file from standard input:

```
python3 src/markdown_footnote_checker.py --stdin < examples/bad.md
```

```
FAIL <stdin>:3: footnote reference 'missing' has no definition
FAIL <stdin>:5: footnote reference 'gone' has no definition
FAIL <stdin>:5: footnote reference 'also-gone' has no definition
FAIL <stdin>:7: footnote definition 'unused' is never referenced
FAIL <stdin>:10: footnote 'twice' is defined more than once
Checked 1 file(s), 5 problem(s) in 1 file(s).
```

Machine-readable output with `--json` (the summary goes to
standard error, so standard output stays clean JSON):

```
python3 src/markdown_footnote_checker.py --json examples/bad.md
```

```
{
  "files": [
    {
      "file": "examples/bad.md",
      "problems": [
        {
          "line": 3,
          "reason": "footnote reference 'missing' has no definition"
        },
        {
          "line": 5,
          "reason": "footnote reference 'gone' has no definition"
        },
        {
          "line": 5,
          "reason": "footnote reference 'also-gone' has no definition"
        },
        {
          "line": 7,
          "reason": "footnote definition 'unused' is never referenced"
        },
        {
          "line": 10,
          "reason": "footnote 'twice' is defined more than once"
        }
      ]
    }
  ],
  "summary": {
    "checked": 1,
    "files_with_problems": 1,
    "problems": 5,
    "skipped": 0
  }
}
```

Exit codes: 0 when every footnote is complete, 1 when
any dangling reference, orphan definition, or duplicate
definition is found, 2 for a usage problem (no Markdown
files given, a bad flag, or a missing file or folder).

## Examples

### 1. A file with five broken footnotes

`examples/bad.md` holds a dangling reference (line 3),
two more on one line (line 5), an orphan definition
(line 7), and a label defined twice (line 10):

```
python3 src/markdown_footnote_checker.py examples/bad.md
```

```
FAIL examples/bad.md:3: footnote reference 'missing' has no definition
FAIL examples/bad.md:5: footnote reference 'gone' has no definition
FAIL examples/bad.md:5: footnote reference 'also-gone' has no definition
FAIL examples/bad.md:7: footnote definition 'unused' is never referenced
FAIL examples/bad.md:10: footnote 'twice' is defined more than once
Checked 1 file(s), 5 problem(s) in 1 file(s).
```

### 2. A broken footnote inside a code block is not a footnote

`examples/fenced.md` has a dangling reference and an
orphan definition inside a fenced code block — they are
examples, so the tool skips them and passes the file:

```
python3 src/markdown_footnote_checker.py examples/fenced.md
```

```
examples/fenced.md: footnotes OK
OK — 1 file(s) checked, all footnotes are complete.
```

### 3. The bundled examples, all at once

```
sh examples/run-example.sh
```

The script checks one clean file (pass), then the file
with broken footnotes (fail, on purpose), then the fenced
example (pass — the broken footnote inside the code block
is skipped), then the whole `examples/` folder (fail, on
purpose — it picks up the five problems in `bad.md`
plus the one in `examples/sub/nested.md`). Its full
output is in `examples/sample-output.md`, ending with
`Checked 5 file(s), 6 problem(s) in 2 file(s).` The
failing runs exit 1, which is the expected result — the
script ends with exit 0 so it can be run as a demo.

## How it is tested

Tests, standard library `unittest` only, no packages to install:

```
python3 tests/test_markdown_footnote_checker.py
```

The tests cover: footnote parsing (clean file, dangling
reference, orphan definition, duplicate definition, two
references on one line, a reference before its
definition, case-insensitive labels, labels with spaces,
a reference inside a definition's own text, an empty
label ignored, empty input, no footnotes), code skipping
(fenced code blocks with backticks and tildes skipped,
inline code spans skipped, unmatched backticks left
alone), file checks (clean file, bad file, missing file,
non-UTF-8 file, input file left unchanged), folder
walking (a direct file always checked, only Markdown
files inside a folder, `.git` never walked,
`--no-recursive`, `--exclude`, a direct file checked
even if excluded, missing path), the CLI (exit 0/1/2,
each flag, `--stdin` good and bad, `--json` output,
`--version`, bad flags, missing paths, empty folders),
running from another working directory (the tool is
checked from a temp folder with relative paths, and
results are matched on file name plus message text, not
on an absolute path), the bundled examples (sample output
compared byte-for-byte against a fresh run, and the
README-quoted outputs checked against it), and hygiene
checks (no placeholder text, no absolute paths, stdlib
imports only, `.env` first in `.gitignore`, CI file runs
the test file).

## Contributing

Small, focused improvements are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

MIT — see [LICENSE](LICENSE).

## Original work

This tool was written from scratch for this repo. The idea
of checking Markdown footnotes is not new, but no rival
does this job — the GitHub search for the exact name and
for the wider field both return 0 repositories (checked
Nov 11, 2026) — and every line of code here is original,
built on nothing but Python's standard library.
