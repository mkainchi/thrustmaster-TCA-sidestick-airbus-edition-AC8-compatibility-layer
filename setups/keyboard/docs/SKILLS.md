# Project-local development skills

Pinned sources live in `.agents/skills/`. The lockfile records commits, origins, licenses and each retained file's SHA-256. Original license notices remain; gamer packages exclude skills. No global plugin or automatic hook is installed.

## Sources and licenses

| Source | Skills | Pinned commit | License |
| --- | --- | --- | --- |
| [Impeccable](https://github.com/pbakaus/impeccable) | impeccable | ffeda44b00b1e39bd901621dcd3a7e44ba184ce1 | Apache-2.0; LICENSE and NOTICE.md retained |
| [Ponytail](https://github.com/DietrichGebert/ponytail) | ponytail, ponytail-audit, ponytail-review | 552acd5efd0aeae2583a12efe39373d2f076f25e | MIT |
| [Superpowers](https://github.com/obra/superpowers) | test-driven-development, systematic-debugging, verification-before-completion | 8ca22dba9a94f28898bbce59f2537ff4d87c747d | MIT |
| [Engineering skills](https://github.com/mattpocock/skills) | codebase-design | f3fc5632f401156837ee3872f14fe33ccf1024ea | MIT |
| [Everything Claude Code](https://github.com/affaan-m/ECC) | python-testing, e2e-testing, frontend-design-direction | ef648e01899ba3e8dc6371642deaaf64b4477775 | MIT |

## Run Impeccable locally

The launcher verifies engine 0.1.11. Keep its engine and reports private and ignored:

```powershell
$env:IMPECCABLE_HOME = (Join-Path (Get-Location) '.local/impeccable')
```

The engine is excluded from the repository and gamer packages. [PRODUCT.md](../PRODUCT.md) holds confirmed requirements; [DESIGN.md](../DESIGN.md) holds interface decisions.

## Working rules

- Use the pinned sources; popularity is not a quality guarantee.
- Run Ponytail in **full** mode. Minimal-testing advice does not override required coverage.
- Validate detector findings with computed styles, keyboard interaction and bounded desktop/narrow inspection.
- Keep detailed audit reports under ignored `.local/`.
- Skills do not authorize publishing, changing drivers, installing global hooks or sharing private data.
