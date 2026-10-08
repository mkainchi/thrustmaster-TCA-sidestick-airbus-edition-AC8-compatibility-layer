# Project-local development skills

Skills are vendored under `.agents/skills/`. `.agents/skills.lock.json` records pinned commits, SHA-256 for every retained file, repository origins and license identifiers. No global plugin or automatic hook is installed. The repository includes the skills' original license notices; gamer ZIPs exclude the entire skills directory.

| Source | Skills | Pinned commit | License |
| --- | --- | --- | --- |
| [Impeccable](https://github.com/pbakaus/impeccable) | impeccable | ffeda44b00b1e39bd901621dcd3a7e44ba184ce1 | Apache-2.0; LICENSE and NOTICE.md retained |
| [Ponytail](https://github.com/DietrichGebert/ponytail) | ponytail, ponytail-audit, ponytail-review | 552acd5efd0aeae2583a12efe39373d2f076f25e | MIT |
| [Superpowers](https://github.com/obra/superpowers) | test-driven-development, systematic-debugging, verification-before-completion | 8ca22dba9a94f28898bbce59f2537ff4d87c747d | MIT |
| [Engineering skills](https://github.com/mattpocock/skills) | codebase-design | f3fc5632f401156837ee3872f14fe33ccf1024ea | MIT |
| [Everything Claude Code](https://github.com/affaan-m/ECC) | python-testing, e2e-testing, frontend-design-direction | ef648e01899ba3e8dc6371642deaaf64b4477775 | MIT |

Popularity informed the prior selection; stars change and are not a quality guarantee. All sources are pinned so installation remains reviewable. The Impeccable launcher verifies engine 0.1.11 before use. Set `IMPECCABLE_HOME` to `.local/impeccable` when running it; its engine and reports remain private and ignored. The engine is not distributed in the repository or gamer packages. Its first context initialization populated PRODUCT.md from confirmed requirements; DESIGN.md records subsequent interface decisions.

The initial Impeccable technical audit found an opportunity to replace the old editor with mode selection, dependency recovery, numbered controls and one save action. Detected inherited-color warnings were manually assessed rather than treated as confirmed contrast failures. The final audit uses computed browser styles, keyboard interaction and bounded desktop/narrow screenshots.

Ponytail audit and architecture review ran in default **full** mode. Their recommendations removed duplicated Xbox bridges and multimedia wrappers: WinMM supplies input, ctypes supplies the ViGEmClient boundary, pathlib/json handle private state, and one generator builds standalone packages. Required request authentication, failure cleanup and coverage gates remain because they directly serve the confirmed requirements. Its advice to minimize tests does not override the explicitly requested scope.

Private detailed audit reports are under `.local/`; they are excluded from releases. Read skill instructions as guidance for this repository, not as authorization to publish, alter system drivers, install global hooks or share private data.
