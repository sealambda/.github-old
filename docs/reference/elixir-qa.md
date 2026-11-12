# Elixir quality checks

These checks are the baseline for an Elixir project of the organization. A
project keeps its own gate that calls them. Credo, Sobelow, `mix_audit` and
Dialyxir are Mix dependencies, declared with `only: [:dev, :test]` and
`runtime: false`. The hub provides the Erlang and Elixir versions in the
`elixir` dev shell (see [Toolchain versions](versions.md)) and the update policy
in `default.json`.

## Checks

| Check            | Command                        | Fails when                                         |
| ---------------- | ------------------------------ | -------------------------------------------------- |
| Format           | `mix format --check-formatted` | A file differs from the formatter output           |
| Credo            | `mix credo --strict`           | A check finds an issue, low priority included      |
| Sobelow          | `mix sobelow --exit low`       | A finding has the confidence level `low` or higher |
| Hex audit        | `mix hex.audit`                | A dependency is retired or has a security advisory |
| Dependency audit | `mix deps.audit`               | A locked dependency has a known vulnerability      |
| Dialyzer         | `mix dialyzer`                 | Dialyzer reports a warning                         |

## Settings

- **Format.** `.formatter.exs` lists the plugins of the project's frameworks.
- **Credo.** `.credo.exs` sets `strict: true`, which has the effect of
  `--strict`.
- **Sobelow.** `mix sobelow --save-config` writes `.sobelow-conf`. Sobelow reads
  it automatically.
- **Dependency audit.** `mix deps.audit` is the `mix_audit` package. It reads
  the advisories of the `elixir-security-advisories` repository.
- **Dialyzer.** `mix dialyzer` is the `dialyxir` package.

## Sources

- [Credo configuration](https://credo.hexdocs.pm/config_file.html)
- [Sobelow](https://sobelow.hexdocs.pm/readme.html)
- [`mix_audit`](https://mix-audit.hexdocs.pm/readme.html)
- [mix hex.audit](https://hex.hexdocs.pm/Mix.Tasks.Hex.Audit.html)
- [Dialyxir](https://dialyxir.hexdocs.pm/readme.html)
