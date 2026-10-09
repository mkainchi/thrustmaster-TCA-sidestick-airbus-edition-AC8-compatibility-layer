# Privacy and sharing

Share only release-tool archives. Keep `.local/`, the editor URL, browser page and console captures private: configuration responses can contain installation paths.

## Local data and access

The offline editor listens on `127.0.0.1` with a random session token. It checks Host and write Origin, limits request size and time, applies a restrictive Content Security Policy, and disables request/error logging.

There is no telemetry, upload, account or cloud service. Official dependency links open only when selected. Anyone who can read the URL or run code as your Windows user can access the editor; it does not protect against a compromised local account.

| Read locally | Purpose |
| --- | --- |
| Installed keyboard layouts and Windows' suggestion | Display choices and translate bindings |
| Controller input through WinMM | Read controls |
| Generic hardware IDs through SetupAPI | Check presence without retrieving instance paths or serials |
| TARGET locations and dependency health | Find prerequisites and check availability |

The application does not read game saves, credentials, network settings or unrelated host inventories.

Each package stores mappings, installation paths, generated scripts, readiness/stop signals, session metadata, previous configuration and migrated legacy originals in ignored `.local/`. Skill reports, traces, screenshots, development environments and build archives also remain ignored.

Public Python runtime dependencies belong in `runtime/` and `dependencies/`, including required `.pyd` extension modules. Development packages may use an ignored `.venv/` or CI's configured Python; they do not need to live in `.local/`. Development packages are not personal data and remain excluded from gamer archives by the release allowlist.

## Check before sharing

Run `check_privacy.cmd` and review custom content yourself. The public project contains product names, generic VID/PID compatibility constants and example bindings. It excludes owner identity, personal paths, serials, USB instance paths, host inventory, game saves and diagnostic dumps.

The checker scans tracked and eligible untracked files, binaries and decompressed ZIP contents for personal paths, unique USB instance paths, local username/Git-author markers and common credential patterns. Markers are read locally, never printed or saved. Findings show redacted filenames and categories, never private matched values.

Hash-bound exceptions allow verified upstream path examples and build metadata, never current identity, credentials or unique USB IDs. Automated scanning cannot detect every identifying sentence or secret.

Use the [release tool](README.md#build-release-archives). Its allowlist excludes private files, `.git/`, caches, diagnostics, development skills and profiles independently of Git ignores. It checks privacy, licenses and naming before packaging. Do not zip the whole folder or force-add ignored files.

## Other identity surfaces

Git author identity, hosting account, repository name, remote URL and published history can identify you separately. This project does not change Git identity, rewrite history or publish the repository. Required third-party attribution describes upstream licensing, not your setup.
