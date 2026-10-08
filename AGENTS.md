# Project instructions

- Read PRODUCT.md and DESIGN.md before changing behavior or the interface.
- Windows x64; plain HTML/CSS/JavaScript and Python. Keep one implementation in app/; regenerate setups/ using tools.distribution. Do not edit generated copies.
- Source, scripts, configuration files and directories use lowercase names. Preserve conventional documentation and upstream dependency filenames.
- Keep personal data, generated scripts, installation paths and audit reports in ignored .local/. Never log device instance paths, serials or private matched values.
- Use project-local skills pinned in .agents/skills.lock.json; see docs/SKILLS.md. Ponytail runs in full mode. Explicit required test coverage takes precedence over minimal-testing advice.
- Do not bundle TARGET binaries/headers/manuals, game assets or manufacturer artwork. Verify dependency hashes, origins and licenses before changing the manifest.
- Run `.local/dev-venv/Scripts/python.exe -m pytest -q`, `npm.cmd test`, `npm.cmd run test:e2e` and `.local/dev-venv/Scripts/python.exe -m tools.distribution check` before completing changes.
- Coverage remains 100% across first-party Python lines/branches and JavaScript statements/lines/functions/branches. Do not add coverage-ignore directives or omit unimported modules.
- Verify physical/gameplay claims separately following docs/VALIDATION.md. Browser fixtures and mocked drivers do not prove gameplay.
- Use allowlisted release tooling. Preserve private settings/backups while regenerating packages. No automatic driver installation, telemetry, global plugins or hooks.
