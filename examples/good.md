# A doc with good footnotes

This sentence has a footnote[^1] and another one[^note].

[^1]: The first footnote.
[^note]: A footnote with a longer label.
    This line continues the definition, indented.

A footnote can point at another footnote[^other] from inside a definition:

[^other]: This definition mentions the first footnote[^1] again.

Write `[^1]` in inline code and it is not a footnote.

A footnote reference can come before its definition[^later].

[^later]: Defined after its first use — order does not matter.

A label with spaces[^my note] works, and case does not matter[^NOTE].

[^my note]: A label with a space in it.
