== good.md: complete footnotes, passes ==
examples/good.md: footnotes OK
OK — 1 file(s) checked, all footnotes are complete.

== bad.md: dangling references, an orphan, a duplicate ==
FAIL examples/bad.md:3: footnote reference 'missing' has no definition
FAIL examples/bad.md:5: footnote reference 'gone' has no definition
FAIL examples/bad.md:5: footnote reference 'also-gone' has no definition
FAIL examples/bad.md:7: footnote definition 'unused' is never referenced
FAIL examples/bad.md:10: footnote 'twice' is defined more than once
Checked 1 file(s), 5 problem(s) in 1 file(s).

== fenced.md: a broken footnote inside a code block is skipped ==
examples/fenced.md: footnotes OK
OK — 1 file(s) checked, all footnotes are complete.

== examples/: a folder walk, six problems ==
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
