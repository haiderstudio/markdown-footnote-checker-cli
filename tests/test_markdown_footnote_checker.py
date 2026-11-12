#!/usr/bin/env python3
"""Tests for markdown-footnote-checker-cli.

Standard library unittest only. Run from the repo root:

    python3 tests/test_markdown_footnote_checker.py

or:

    python3 -m unittest discover -s tests

The tests pass from any working directory: every path
used here is built from this file's own location, and
checks on CLI output match on the file name plus the
message text, never on an absolute path.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "markdown_footnote_checker.py"
sys.path.insert(0, str(ROOT / "src"))

import markdown_footnote_checker as tool  # noqa: E402


def run_cli(*args, stdin_text=None, cwd=None):
    """Run the tool as a subprocess and return (returncode, stdout, stderr)."""
    result = subprocess.run(
        [sys.executable, str(SRC), *args],
        input=stdin_text,
        capture_output=True,
        text=True,
        cwd=str(cwd or ROOT),
    )
    return result.returncode, result.stdout, result.stderr


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class TestStripInlineCode(unittest.TestCase):
    def test_plain_text_unchanged(self):
        self.assertEqual(
            tool._strip_inline_code("see note[^1] here"),
            "see note[^1] here",
        )

    def test_single_code_span_removed(self):
        self.assertEqual(
            tool._strip_inline_code("write `[^1]` in code"),
            "write  in code",
        )

    def test_double_backtick_span_removed(self):
        self.assertEqual(
            tool._strip_inline_code("write `` `[^1]` `` here"),
            "write  here",
        )

    def test_unmatched_backtick_left_alone(self):
        self.assertEqual(
            tool._strip_inline_code("a stray ` and [^1]"),
            "a stray ` and [^1]",
        )

    def test_code_span_with_footnote_removed(self):
        self.assertEqual(
            tool._find_references("write `[^1]` in code"),
            [],
        )


class TestCheckLines(unittest.TestCase):
    def test_clean_file(self):
        lines = [
            "Text with a note[^1] and another[^note].",
            "",
            "[^1]: The first footnote.",
            "[^note]: A longer label.",
        ]
        self.assertEqual(tool.check_lines(lines), [])

    def test_dangling_reference(self):
        problems = tool.check_lines(["Text[^missing]."])
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0]["line"], 1)
        self.assertEqual(
            problems[0]["reason"],
            "footnote reference 'missing' has no definition",
        )

    def test_orphan_definition(self):
        problems = tool.check_lines(["[^unused]: Never used."])
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0]["line"], 1)
        self.assertEqual(
            problems[0]["reason"],
            "footnote definition 'unused' is never referenced",
        )

    def test_duplicate_definition(self):
        lines = ["[^twice]: First.", "[^twice]: Second."]
        problems = tool.check_lines(lines)
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0]["line"], 2)
        self.assertEqual(
            problems[0]["reason"],
            "footnote 'twice' is defined more than once",
        )

    def test_duplicate_definition_not_also_an_orphan(self):
        # A label defined twice and never referenced is one
        # problem (the duplicate), not two: its first
        # definition must not also be reported as an orphan.
        lines = ["[^twice]: First.", "[^twice]: Second."]
        problems = tool.check_lines(lines)
        self.assertEqual(len(problems), 1)
        self.assertNotIn("never referenced", problems[0]["reason"])

    def test_duplicate_definition_that_is_referenced(self):
        lines = ["Text[^a].", "", "[^a]: One.", "[^a]: Two."]
        problems = tool.check_lines(lines)
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0]["line"], 4)
        self.assertIn("more than once", problems[0]["reason"])

    def test_two_references_on_one_line(self):
        lines = ["One[^gone] and two[^also-gone]."]
        problems = tool.check_lines(lines)
        self.assertEqual(len(problems), 2)
        self.assertEqual(
            [p["line"] for p in problems], [1, 1]
        )

    def test_reference_before_definition(self):
        lines = ["Text[^later].", "", "[^later]: Defined after use."]
        self.assertEqual(tool.check_lines(lines), [])

    def test_labels_match_without_regard_to_case(self):
        lines = ["Text[^NOTE].", "", "[^note]: Lower case definition."]
        self.assertEqual(tool.check_lines(lines), [])

    def test_label_with_spaces(self):
        lines = ["Text[^my note].", "", "[^my note]: A spaced label."]
        self.assertEqual(tool.check_lines(lines), [])

    def test_reference_inside_definition_text_counts(self):
        lines = [
            "Text[^other].",
            "",
            "[^other]: This mentions the first[^1] again.",
            "[^1]: The first footnote.",
        ]
        self.assertEqual(tool.check_lines(lines), [])

    def test_dangling_reference_inside_definition_text(self):
        lines = [
            "Text[^other].",
            "",
            "[^other]: This mentions a missing[^gone] one.",
        ]
        problems = tool.check_lines(lines)
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0]["line"], 3)
        self.assertIn("'gone'", problems[0]["reason"])

    def test_empty_label_ignored(self):
        self.assertEqual(tool.check_lines(["Text[^]."]), [])

    def test_problems_sorted_by_line(self):
        lines = ["[^orphan]: Def.", "", "Text[^dangling]."]
        problems = tool.check_lines(lines)
        self.assertEqual([p["line"] for p in problems], [1, 3])

    def test_definition_indented_three_spaces(self):
        lines = ["Text[^a].", "", "   [^a]: Indented three spaces."]
        self.assertEqual(tool.check_lines(lines), [])

    def test_definition_indented_four_spaces_is_not_a_definition(self):
        # Four spaces is an indented code block, not a
        # definition, so the label on that line is read as
        # a reference with no definition.
        lines = ["    [^a]: Indented four spaces."]
        problems = tool.check_lines(lines)
        self.assertEqual(len(problems), 1)
        self.assertIn("has no definition", problems[0]["reason"])

    def test_empty_input(self):
        self.assertEqual(tool.check_lines([]), [])

    def test_no_footnotes(self):
        self.assertEqual(
            tool.check_lines(["# Title", "", "Some text."]), []
        )


class TestFencedCodeBlocks(unittest.TestCase):
    def test_backtick_fence_skipped(self):
        lines = [
            "```",
            "Text[^missing].",
            "[^unused]: Never referenced.",
            "```",
            "Text[^1].",
            "",
            "[^1]: The real one.",
        ]
        self.assertEqual(tool.check_lines(lines), [])

    def test_tilde_fence_skipped(self):
        lines = [
            "~~~",
            "Text[^missing].",
            "~~~",
        ]
        self.assertEqual(tool.check_lines(lines), [])

    def test_inline_code_span_skipped(self):
        lines = ["Write `[^missing]` in code.", "", "[^1]: Real."]
        problems = tool.check_lines(lines)
        # Only the orphan definition is a problem; the
        # code-span reference is not.
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0]["line"], 3)
        self.assertIn("never referenced", problems[0]["reason"])

    def test_fence_with_language_skipped(self):
        lines = [
            "```markdown",
            "Text[^missing].",
            "```",
        ]
        self.assertEqual(tool.check_lines(lines), [])


class TestCheckFile(unittest.TestCase):
    def test_clean_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(
                Path(tmp) / "doc.md",
                "Text[^1].\n\n[^1]: The one.\n",
            )
            problems, skipped = tool.check_file(path)
            self.assertEqual(problems, [])
            self.assertFalse(skipped)

    def test_bad_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(Path(tmp) / "doc.md", "Text[^gone].\n")
            problems, _ = tool.check_file(path)
            self.assertEqual(len(problems), 1)
            self.assertEqual(problems[0]["line"], 1)

    def test_missing_file_is_a_problem(self):
        problems, _ = tool.check_file(Path("/nonexistent/doc.md"))
        self.assertEqual(len(problems), 1)
        self.assertIn("cannot read file", problems[0]["reason"])

    def test_non_utf8_file_is_a_problem(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "doc.md"
            path.write_bytes(b"\xff\xfe bad bytes\n")
            problems, _ = tool.check_file(path)
            self.assertEqual(len(problems), 1)
            self.assertIn("UTF-8", problems[0]["reason"])

    def test_file_left_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(Path(tmp) / "doc.md", "Text[^gone].\n")
            before = path.read_bytes()
            tool.check_file(path)
            self.assertEqual(path.read_bytes(), before)


class TestGather(unittest.TestCase):
    def test_direct_file_always_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(Path(tmp) / "notes.txt", "Text[^gone].\n")
            entries, checked, _ = tool.gather([str(path)], [], True)
            self.assertEqual(len(checked), 1)
            self.assertEqual(len(entries), 1)

    def test_folder_only_checks_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "a.md", "Text[^gone].\n")
            write(root / "b.markdown", "Text[^gone].\n")
            write(root / "c.txt", "Text[^gone].\n")
            entries, checked, _ = tool.gather([str(root)], [], True)
            self.assertEqual(len(checked), 2)
            self.assertEqual(len(entries), 2)

    def test_git_folder_never_walked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / ".git" / "a.md", "Text[^gone].\n")
            write(root / "a.md", "Text[^1].\n\n[^1]: One.\n")
            _entries, checked, _ = tool.gather([str(root)], [], True)
            self.assertEqual(len(checked), 1)
            self.assertEqual(checked[0]["file"], str(root / "a.md"))

    def test_no_recursive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "a.md", "Text[^1].\n\n[^1]: One.\n")
            write(root / "sub" / "b.md", "Text[^gone].\n")
            _entries, checked, _ = tool.gather([str(root)], [], False)
            self.assertEqual(len(checked), 1)

    def test_exclude_pattern(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "a.md", "Text[^gone].\n")
            write(root / "sub" / "b.md", "Text[^gone].\n")
            entries, checked, skipped = tool.gather(
                [str(root)], ["sub/b.md"], True
            )
            self.assertEqual(len(checked), 1)
            self.assertEqual(len(entries), 1)
            self.assertEqual(len(skipped), 1)

    def test_direct_file_checked_even_if_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(Path(tmp) / "a.md", "Text[^gone].\n")
            entries, checked, _ = tool.gather([str(path)], ["a.md"], True)
            self.assertEqual(len(checked), 1)
            self.assertEqual(len(entries), 1)

    def test_missing_path_raises(self):
        with self.assertRaises(FileNotFoundError):
            tool.gather(["/nonexistent/path"], [], True)


class TestCLI(unittest.TestCase):
    def test_clean_file_exit_0(self):
        code, out, _err = run_cli("examples/good.md")
        self.assertEqual(code, 0)
        self.assertIn("examples/good.md: footnotes OK", out)
        self.assertIn("all footnotes are complete", out)

    def test_bad_file_exit_1(self):
        code, out, _err = run_cli("examples/bad.md")
        self.assertEqual(code, 1)
        self.assertIn(
            "FAIL examples/bad.md:3: footnote reference 'missing' "
            "has no definition",
            out,
        )
        self.assertIn(
            "FAIL examples/bad.md:5: footnote reference 'gone' "
            "has no definition",
            out,
        )
        self.assertIn(
            "FAIL examples/bad.md:5: footnote reference 'also-gone' "
            "has no definition",
            out,
        )
        self.assertIn(
            "FAIL examples/bad.md:7: footnote definition 'unused' "
            "is never referenced",
            out,
        )
        self.assertIn(
            "FAIL examples/bad.md:10: footnote 'twice' is defined "
            "more than once",
            out,
        )
        self.assertIn("Checked 1 file(s), 5 problem(s) in 1 file(s).", out)

    def test_fenced_file_exit_0(self):
        code, out, _err = run_cli("examples/fenced.md")
        self.assertEqual(code, 0)
        self.assertIn("footnotes OK", out)

    def test_folder_walk(self):
        code, out, _err = run_cli("examples/")
        self.assertEqual(code, 1)
        self.assertIn("Checked 5 file(s), 6 problem(s) in 2 file(s).", out)
        self.assertIn(
            "FAIL examples/sub/nested.md:3: footnote reference 'lost' "
            "has no definition",
            out,
        )

    def test_no_recursive_flag(self):
        code, out, _err = run_cli("--no-recursive", "examples/")
        self.assertEqual(code, 1)
        self.assertIn("Checked 4 file(s), 5 problem(s) in 1 file(s).", out)

    def test_exclude_flag(self):
        code, out, _err = run_cli(
            "--exclude", "sub/nested.md", "examples/"
        )
        self.assertEqual(code, 1)
        self.assertIn("Checked 4 file(s), 5 problem(s) in 1 file(s).", out)
        self.assertNotIn("nested.md", out)

    def test_stdin(self):
        code, out, _err = run_cli(
            "--stdin", stdin_text="Text[^gone].\n"
        )
        self.assertEqual(code, 1)
        self.assertIn("FAIL <stdin>:1:", out)

    def test_stdin_clean(self):
        code, out, _err = run_cli(
            "--stdin", stdin_text="Text[^1].\n\n[^1]: One.\n"
        )
        self.assertEqual(code, 0)
        self.assertIn("all footnotes are complete", out)

    def test_json_output(self):
        code, out, err = run_cli("--json", "examples/bad.md")
        self.assertEqual(code, 1)
        data = json.loads(out)
        self.assertEqual(data["summary"]["checked"], 1)
        self.assertEqual(data["summary"]["problems"], 5)
        self.assertEqual(data["summary"]["files_with_problems"], 1)
        self.assertEqual(len(data["files"][0]["problems"]), 5)
        self.assertEqual(data["files"][0]["problems"][0]["line"], 3)
        self.assertIn("Checked 1 file(s), 5 problem(s)", err)

    def test_json_clean(self):
        code, out, err = run_cli("--json", "examples/good.md")
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["summary"]["problems"], 0)
        self.assertIn("all footnotes are complete", err)

    def test_version(self):
        code, out, _err = run_cli("--version")
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "markdown-footnote-checker-cli 1.0.0")

    def test_missing_path_exit_2(self):
        code, _out, err = run_cli("/nonexistent/doc.md")
        self.assertEqual(code, 2)
        self.assertIn("no such file or folder", err)

    def test_no_paths_exit_2(self):
        code, _out, err = run_cli()
        self.assertEqual(code, 2)
        self.assertIn("no Markdown files to check", err)

    def test_empty_folder_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _out, err = run_cli(tmp)
            self.assertEqual(code, 2)
            self.assertIn("no Markdown files to check", err)

    def test_bad_flag_exit_2(self):
        code, _out, err = run_cli("--nope")
        self.assertEqual(code, 2)
        self.assertIn("unrecognized arguments", err)


class TestCwdRobustness(unittest.TestCase):
    """The tool and its tests must work from any directory.

    Checks here match on the file name plus the message
    text, never on an absolute path — the CLI may print
    paths relative to the working directory.
    """

    def test_cli_from_temp_dir_with_relative_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copy(ROOT / "examples" / "bad.md", Path(tmp) / "bad.md")
            code, out, _err = run_cli("bad.md", cwd=tmp)
            self.assertEqual(code, 1)
            self.assertIn("FAIL bad.md:3:", out)
            self.assertIn(
                "footnote reference 'missing' has no definition", out
            )
            self.assertIn("Checked 1 file(s), 5 problem(s)", out)

    def test_cli_from_tmp_with_absolute_example_path(self):
        code, out, _err = run_cli(
            str(ROOT / "examples" / "bad.md"), cwd="/tmp"
        )
        self.assertEqual(code, 1)
        # Match on the file-name suffix, not the full path.
        self.assertIn("bad.md:3:", out)
        self.assertIn(
            "footnote reference 'missing' has no definition", out
        )
        self.assertIn("bad.md:10:", out)
        self.assertIn("footnote 'twice' is defined more than once", out)

    def test_cli_from_goal_dir(self):
        goal = ROOT.parent.parent
        code, out, _err = run_cli(
            str(ROOT / "examples" / "good.md"), cwd=str(goal)
        )
        self.assertEqual(code, 0)
        self.assertIn("good.md: footnotes OK", out)
        self.assertIn("all footnotes are complete", out)


class TestBundledExamples(unittest.TestCase):
    def test_sample_output_matches_fresh_run(self):
        result = subprocess.run(
            ["sh", str(ROOT / "examples" / "run-example.sh")],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        self.assertEqual(result.returncode, 0)
        expected = (ROOT / "examples" / "sample-output.md").read_text(
            encoding="utf-8"
        )
        self.assertEqual(result.stdout, expected)

    def test_run_example_script_exits_zero(self):
        result = subprocess.run(
            ["sh", str(ROOT / "examples" / "run-example.sh")],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        self.assertEqual(result.returncode, 0)

    def test_readme_quotes_real_output(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for line in [
            "examples/good.md: footnotes OK",
            "OK — 1 file(s) checked, all footnotes are complete.",
            "FAIL examples/bad.md:3: footnote reference 'missing' has no definition",
            "FAIL examples/bad.md:5: footnote reference 'gone' has no definition",
            "FAIL examples/bad.md:7: footnote definition 'unused' is never referenced",
            "FAIL examples/bad.md:10: footnote 'twice' is defined more than once",
            "Checked 1 file(s), 5 problem(s) in 1 file(s).",
            "FAIL examples/sub/nested.md:3: footnote reference 'lost' has no definition",
            "Checked 5 file(s), 6 problem(s) in 2 file(s).",
            "Checked 4 file(s), 5 problem(s) in 1 file(s).",
        ]:
            self.assertIn(line, readme, f"README is missing real output: {line}")


class TestHygiene(unittest.TestCase):
    def _repo_files(self):
        # Hygiene scans exclude .git, __pycache__, and tests/ —
        # the test file itself names the banned words it scans
        # for, and its own path strings are not shipped content.
        for dirpath, dirnames, filenames in os.walk(ROOT):
            dirnames[:] = sorted(
                d
                for d in dirnames
                if d not in (".git", "__pycache__", "tests")
            )
            for name in filenames:
                yield Path(dirpath) / name

    def test_no_placeholder_text(self):
        banned = ["TODO", "coming soon", "lorem", "Lorem", "FIXME", "XXX"]
        for path in self._repo_files():
            if path.suffix in (".pyc",):
                continue
            text = path.read_bytes().decode("utf-8", errors="ignore")
            for word in banned:
                self.assertNotIn(
                    word, text, f"{word} found in {path.relative_to(ROOT)}"
                )

    def test_no_absolute_local_paths(self):
        for path in self._repo_files():
            text = path.read_bytes().decode("utf-8", errors="ignore")
            self.assertNotIn(
                "/home/hatch", text, f"absolute path in {path.relative_to(ROOT)}"
            )

    def test_stdlib_imports_only(self):
        source = (ROOT / "src" / "markdown_footnote_checker.py").read_text(
            encoding="utf-8"
        )
        stdlib = {
            "argparse",
            "fnmatch",
            "json",
            "os",
            "re",
            "sys",
            "pathlib",
        }
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith("import "):
                names = stripped[7:].split(",")
                for name in names:
                    self.assertIn(
                        name.strip().split()[0], stdlib, f"non-stdlib import: {line}"
                    )
            elif stripped.startswith("from "):
                module = stripped[5:].split()[0]
                self.assertIn(
                    module.split(".")[0], stdlib, f"non-stdlib import: {line}"
                )

    def test_gitignore_first_line_is_env(self):
        lines = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0], ".env")

    def test_ci_file_runs_the_test_file(self):
        # Substring marker checks only — never an exact
        # comparison against another repo's ci.yml, and
        # never a read of another repo's files.
        ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("checkout", ci)
        self.assertIn("setup-python", ci)
        self.assertIn("tests/test_markdown_footnote_checker.py", ci)
        self.assertIn("push", ci)
        self.assertIn("pull_request", ci)


if __name__ == "__main__":
    unittest.main()
