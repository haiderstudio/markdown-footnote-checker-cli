#!/bin/sh
# Check the bundled examples. The failing runs exit 1 on purpose,
# so each one ends with "|| true"; the script itself ends with
# exit 0 so it can be run as a demo. Run from the repo root:
# sh examples/run-example.sh
cd "$(dirname "$0")/.."
echo "== good.md: complete footnotes, passes =="
python3 src/markdown_footnote_checker.py examples/good.md || true
echo
echo "== bad.md: dangling references, an orphan, a duplicate =="
python3 src/markdown_footnote_checker.py examples/bad.md || true
echo
echo "== fenced.md: a broken footnote inside a code block is skipped =="
python3 src/markdown_footnote_checker.py examples/fenced.md || true
echo
echo "== examples/: a folder walk, six problems =="
python3 src/markdown_footnote_checker.py examples/ || true
