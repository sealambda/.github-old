# Add third-party content

Add a file that someone else wrote, or that you derived from another work, and
record its source, copyright and license. The flake check `licenses` can't
tell that a file is third-party, so this procedure is the control. The facts
are in [Licensing](../reference/licensing.md).

## Before you start

- You know the source of the file: the repository or the page, and the
  version, tag or commit that you copied.
- The license of the source allows the hub to hold and redistribute the file.
  Ask a maintainer when you can't tell.

## Decide whether the content is third-party

Content is third-party when you copy text, code or configuration from another
work, or when you change such a copy. These cases aren't third-party:

- You write the file yourself, even when it follows a published format.
- The hub names a tool or an action and holds no copy of it.
- Nix builds the content from nixpkgs when a check runs.

## Steps

1. Read the license terms of the source. Find its copyright notice, in the
   license file or in the header of the file, and its SPDX license expression.
2. Add the file to the repository.
3. Add a table at the end of `REUSE.toml`, after the table for all files. The
   last table that matches a file is the only one that applies to it, so its
   keys list every copyright notice and the whole license expression. Set
   `precedence = "override"`, so that the table wins over any text in the file:

   ```toml
   [[annotations]]
   path = "templates/example.md.tmpl"
   precedence = "override"
   SPDX-FileCopyrightText = [
     "2020 Jane Doe",
     "2026 Sealambda",
   ]
   SPDX-License-Identifier = "MIT"
   ```

   List the notice of the source first. Add the line of Sealambda when you
   changed the file. Put a comment above the table with the source, the version
   and the reason for the expression.
4. Add the text of each new license to `LICENSES/`. Fetch it from the SPDX
   License List:

   ```sh
   nix shell --inputs-from . nixpkgs#reuse -c reuse download MIT
   ```

   The command writes `LICENSES/MIT.txt`. A license that isn't on the list
   needs a `LicenseRef-` identifier and a file that you write:
   `LICENSES/LicenseRef-name.txt`.
5. Add a row to the table in
   [Licensing](../reference/licensing.md#third-party-content) with the file,
   the source, the version, the license and the local changes.
6. Run the checks. Nix reads only the files that Git knows, so add every new
   file with `git add -N <path>` first: the third-party file and each text
   that step 4 added to `LICENSES/`:

   ```sh
   nix flake check
   ```

## Check the result

`nix flake check` shows only the exit status of the check, which is 0 when it
passes. To read the report, run the check alone. It ends with the line
"Congratulations! Your project is compliant":

```sh
nix build .#checks.<system>.licenses -L
```

Replace `<system>` with your system, for example `x86_64-linux`. To see the
data of the file, run `reuse lint --json` in a shell with the `reuse` tool and
find the path in the output. The entry lists the copyright notices and the
license expression that apply.

## If it fails

- **Missing licenses.** A license that a table names has no text in
  `LICENSES/`. Run step 4, and run `git add -N` on the text.
- **A file takes its notice or license from its own text.** The file holds the
  word `Copyright` followed by a space, or an SPDX tag, and its table doesn't
  win. Set `precedence = "override"` in the table of the file.
- **Unused licenses.** `LICENSES/` holds a text that no table names. Delete
  the text, or fix the expression in the table.
- **Bad licenses.** A file in `LICENSES/` has a name that isn't an SPDX
  identifier followed by an extension. Rename it, or delete it when it isn't a
  license text.
- **`LICENSE differs from LICENSES/MPL-2.0.txt`.** Copy `LICENSES/MPL-2.0.txt`
  over `LICENSE`. The check ignores a space or a tab at the end of a line.

## Related

- [Licensing](../reference/licensing.md)
- [REUSE specification 3.3](https://reuse.software/spec-3.3/)
