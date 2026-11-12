#!/usr/bin/env python3
"""Check Markdown footnotes are complete both ways, fail CI on a gap.

Run: python3 src/markdown_footnote_checker.py examples/good.md
     python3 src/markdown_footnote_checker.py examples/
     python3 src/markdown_footnote_checker.py --json examples/bad.md

The problem is quiet: a footnote reference with no
definition renders as literal "[^1]" text in the
reader's face, and an orphan definition sits at the
bottom of the doc pointing at nothing. Docs writers
renumber and delete footnotes by hand all the time.
This tool reads each Markdown file, finds every
footnote reference "[^label]" and every definition
"[^label]: ...", checks each reference has a matching
definition and each definition is actually referenced,
reports every dangling reference and orphan definition
with its file and line number, and exits 1 when any
problem is found, so it can fail a CI run. A clean file
exits 0.

A reference is "[^label]" anywhere in the text. A
definition is a line that starts with "[^label]:" (up
to three spaces of indent — four spaces is an indented
code block, not a definition). Labels match without
regard to case, so "[^Note]" matches "[^note]: ...".
A label defined twice is one problem, reported at the
second definition. References inside a definition's
own text count — a definition can point at another
footnote. References may come before or after their
definition; order does not matter.

Footnotes inside fenced code blocks (``` or ~~~) are
skipped — they are examples, not footnotes. Footnotes
inside inline code spans ("`[^1]`") are skipped too —
they are code, not footnotes.

It never rewrites a file. It is report-only and runs
fully offline: it sends nothing anywhere and needs no
API key.

Exit codes: 0 when every footnote is complete, 1 when
any dangling reference, orphan definition, or duplicate
definition is found, 2 for a usage or input problem (a
missing path, a bad flag, a bad --exclude value, or no
Markdown file to check).

Python standard library only.
"""

import argparse
import fnmatch
import json
import os
import re
import sys
from pathlib import Path

VERSION = "1.0.0"

MARKDOWN_EXTENSIONS = {".md", ".markdown"}

_REFERENCE = re.compile(r"\[\^([^\]\n]+)\]")
_DEFINITION = re.compile(r"^ {0,3}\[\^([^\]\n]+)\]:")
_FENCE = re.compile(r"^\s*(```|~~~)")


def _normalise(label):
    """Return the label as it is matched: stripped, lower case."""
    return label.strip().lower()


def _strip_inline_code(line):
    """Return the line with inline code spans removed.

    A code span starts with a run of backticks and ends at
    the next run of the same length. Text inside a span is
    code, not a footnote, so "[^1]" written inside backticks
    is not a reference. An unmatched run of backticks is
    left in place — it is not a code span.
    """
    out = []
    index = 0
    total = len(line)
    while index < total:
        if line[index] != "`":
            out.append(line[index])
            index += 1
            continue
        run = 0
        while index + run < total and line[index + run] == "`":
            run += 1
        closing = line.find("`" * run, index + run)
        if closing == -1:
            out.append(line[index : index + run])
            index += run
        else:
            index = closing + run
    return "".join(out)


def _find_references(text):
    """Return the labels of every footnote reference in text.

    Each item is (label as written). Inline code spans are
    stripped first, so "[^1]" inside backticks is not a
    reference.
    """
    clean = _strip_inline_code(text)
    return [match.group(1) for match in _REFERENCE.finditer(clean)]


def check_lines(lines):
    """Return the footnote problems in one file's lines.

    lines is a list of the file's lines in order. Each
    problem is a dict with "line" (the line number,
    starting at 1) and "reason". Problems are sorted by
    line number. Footnotes inside fenced code blocks and
    inline code spans are skipped.
    """
    problems = []
    definitions = {}
    duplicates = set()
    references = []
    in_fence = False
    for number, line in enumerate(lines, start=1):
        if _FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = _DEFINITION.match(line)
        if match:
            label = match.group(1)
            key = _normalise(label)
            if key in definitions:
                duplicates.add(key)
                problems.append(
                    {
                        "line": number,
                        "reason": (
                            f"footnote '{label}' is defined "
                            "more than once"
                        ),
                    }
                )
            else:
                definitions[key] = (number, label)
            # A definition's own text can reference another
            # footnote, so scan what follows the colon.
            rest = line[match.end() :]
            for ref in _find_references(rest):
                references.append((number, ref))
            continue
        for ref in _find_references(line):
            references.append((number, ref))
    for number, ref in references:
        if _normalise(ref) not in definitions:
            problems.append(
                {
                    "line": number,
                    "reason": (
                        f"footnote reference '{ref}' "
                        "has no definition"
                    ),
                }
            )
    referenced = {_normalise(ref) for _number, ref in references}
    for key, (number, label) in definitions.items():
        # A label defined twice is already reported as a
        # duplicate; reporting its first definition as an
        # orphan too would be the same problem twice.
        if key not in referenced and key not in duplicates:
            problems.append(
                {
                    "line": number,
                    "reason": (
                        f"footnote definition '{label}' "
                        "is never referenced"
                    ),
                }
            )
    problems.sort(key=lambda problem: problem["line"])
    return problems


def check_file(path):
    """Return (problems, skipped) for one Markdown file.

    skipped is always False — nothing is skipped, a file
    that cannot be read is a problem.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="strict")
    except UnicodeDecodeError:
        return (
            [{"line": 0, "reason": "not readable as UTF-8 text"}],
            False,
        )
    except OSError as exc:
        return (
            [{"line": 0, "reason": f"cannot read file: {exc.strerror}"}],
            False,
        )
    return check_lines(text.splitlines()), False


def _is_markdown(name):
    return Path(name).suffix.lower() in MARKDOWN_EXTENSIONS


def gather(paths, exclude, recursive):
    """Walk the given paths and return (entries, checked, skipped).

    entries is a list of (file, problem); checked is a list
    of one dict per file the tool tried, with file and
    problems; skipped is a list of files skipped by
    --exclude. A file passed on the command line is always
    checked, even if it matches --exclude and even if it
    has no Markdown extension. Inside a folder, only
    .md and .markdown files are checked.
    """
    entries = []
    checked = []
    skipped = []
    for raw in paths:
        path = Path(raw)
        if not path.exists():
            raise FileNotFoundError(raw)
        if path.is_file():
            problems, _was_skipped = check_file(path)
            checked.append({"file": str(path), "problems": problems})
            for problem in problems:
                entries.append((str(path), problem))
            continue
        if recursive:
            for dirpath, dirnames, filenames in _walk(path):
                for name in filenames:
                    if not _is_markdown(name):
                        continue
                    candidate = Path(dirpath) / name
                    if _excluded(candidate, path, exclude):
                        skipped.append(str(candidate))
                        continue
                    problems, _was_skipped = check_file(candidate)
                    checked.append(
                        {"file": str(candidate), "problems": problems}
                    )
                    for problem in problems:
                        entries.append((str(candidate), problem))
        else:
            for candidate in sorted(path.iterdir()):
                if not candidate.is_file():
                    continue
                if not _is_markdown(candidate.name):
                    continue
                if _excluded(candidate, path, exclude):
                    skipped.append(str(candidate))
                    continue
                problems, _was_skipped = check_file(candidate)
                checked.append(
                    {"file": str(candidate), "problems": problems}
                )
                for problem in problems:
                    entries.append((str(candidate), problem))
    return entries, checked, skipped


def _walk(root):
    """os.walk that never enters .git and never follows links."""
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d != ".git")
        yield dirpath, dirnames, sorted(filenames)


def _excluded(candidate, root, patterns):
    name = candidate.name
    try:
        rel = str(candidate.relative_to(root))
    except ValueError:
        rel = name
    return any(
        fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(rel, pattern)
        for pattern in patterns
    )


def _format_problem(location, problem):
    return f"FAIL {location}:{problem['line']}: {problem['reason']}"


def _summary_line(checked, problems):
    total = len(problems)
    bad_files = len({f for f, _p in problems})
    if total:
        return (
            f"Checked {len(checked)} file(s), {total} "
            f"problem(s) in {bad_files} file(s)."
        )
    return (
        f"OK — {len(checked)} file(s) checked, "
        f"all footnotes are complete."
    )


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="markdown-footnote-checker-cli",
        description="Check Markdown footnotes are complete both ways.",
    )
    parser.add_argument(
        "paths", nargs="*", help="files or folders to check"
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="read one Markdown file from standard input",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="PATTERN",
        help="skip files matching this glob (repeatable)",
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="do not walk into subfolders",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print the result as JSON (summary goes to stderr)",
    )
    parser.add_argument("--version", action="store_true", help="print the version")
    args = parser.parse_args(argv)

    if args.version:
        print(f"markdown-footnote-checker-cli {VERSION}")
        return 0

    entries = []
    checked = []
    skipped = []
    try:
        if args.paths:
            found, found_checked, found_skipped = gather(
                args.paths,
                args.exclude,
                not args.no_recursive,
            )
            entries.extend(found)
            checked.extend(found_checked)
            skipped.extend(found_skipped)
    except FileNotFoundError as exc:
        print(f"error: no such file or folder: {exc}", file=sys.stderr)
        return 2

    if args.stdin:
        text = sys.stdin.read()
        problems = check_lines(text.splitlines())
        checked.append({"file": "<stdin>", "problems": problems})
        for problem in problems:
            entries.append(("<stdin>", problem))

    if not checked:
        print("error: no Markdown files to check", file=sys.stderr)
        return 2

    problems = entries
    bad_files = len({f for f, _p in problems})
    total = len(problems)
    summary = _summary_line(checked, problems)

    if args.json:
        files = []
        for entry in checked:
            files.append(
                {
                    "file": entry["file"],
                    "problems": entry["problems"],
                }
            )
        result = {
            "files": files,
            "summary": {
                "checked": len(checked),
                "files_with_problems": bad_files,
                "problems": total,
                "skipped": len(skipped),
            },
        }
        print(json.dumps(result, indent=2))
        print(summary, file=sys.stderr)
        return 1 if problems else 0

    for entry in checked:
        if entry["problems"]:
            for problem in entry["problems"]:
                print(_format_problem(entry["file"], problem))
        else:
            print(f"{entry['file']}: footnotes OK")
    print(summary)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
