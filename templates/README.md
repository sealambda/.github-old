# Templates

Copy a template into your repository when you start a page or a decision record.
Drop the `.tmpl` suffix. The suffix keeps the placeholders out of the Markdown
checks. Replace every `{placeholder}`, and delete the optional parts you do not
need.

| Template              | Use it for                             |
| --------------------- | -------------------------------------- |
| `adr.md.tmpl`         | A decision record in `docs/decisions/` |
| `tutorial.md.tmpl`    | A lesson that teaches by doing         |
| `how-to.md.tmpl`      | The steps to reach one goal            |
| `reference.md.tmpl`   | Facts about one thing                  |
| `explanation.md.tmpl` | The reasons behind a design            |

The page templates follow [Diátaxis](https://diataxis.fr/). One page has one
type: do not mix a tutorial with reference facts.

## Source of `adr.md.tmpl`

`adr.md.tmpl` is the [MADR](https://adr.github.io/madr/) 4.0.0 template,
`template/adr-template.md` in the
[adr/madr](https://github.com/adr/madr/tree/4.0.0) repository, with one change
to the front matter. The `status` line reads `proposed`, with a comment that
lists the three values of the hub: `proposed`, `accepted` and `rejected`. A
comment also names the required keys. MADR is available under the MIT license or
CC0 1.0. Name a record `NNNN-title-with-dashes.md`, and number the records in
the order you write them. The
[decision records reference](../docs/reference/decision-records.md) defines the
format.
