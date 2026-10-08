# TCA Airbus configuration

Configure a Thrustmaster TCA Sidestick Airbus Edition (Pilot or Copilot) and TCA Quadrant Eng 1&2 on Windows x64. Choose keyboard output, an emulated Xbox controller, or TARGET followed by Xbox emulation. Configuration runs in an offline browser page; mappings remain private on your computer.

## Two commands

1. Connect both devices. Run `configure.cmd`, choose a mode and edit its mappings. For keyboard mode, explicitly choose the installed Windows keyboard layout used by your game. Windows offers a suggestion without selecting it for you.
2. Review dependency status, install any missing prerequisites using the official links, recheck, then **Save this mode**. Run `emulate.cmd` before launching your game. Keep its window open.

Run `emulate.cmd --stop`, or press Ctrl+C in the emulation window, to release controls. Close the configuration window with Ctrl+C when finished. No administrator rights are needed for configuration; installing an external driver may require them. The application never installs a driver or accepts its license for you.

| Mode | Input and output | External prerequisites |
| --- | --- | --- |
| `keyboard` | TARGET translates stick movement into flight keys, POV into camera keys, and buttons into editable keys | TARGET; Microsoft Visual C++ x64 runtime |
| `xbox` | Native Windows joystick input → ViGEmClient → Xbox/XInput | ViGEmBus; Microsoft Visual C++ x64 runtime |
| `target-xbox` | TARGET Combined → the same Xbox bridge → Xbox/XInput | TARGET; ViGEmBus; Microsoft Visual C++ x64 runtime |

The standalone directories under `setups/` contain their own runtime, dependencies and README. Their configure command opens that package's mode. Each extracted package stores its own private settings. Use only one package at a time with these devices; stop its emulation before starting another.

## Dependency installation

- [TARGET and device downloads](https://support.thrustmaster.com/en/product/tca-sidestick-airbus-edition-en/): install TARGET yourself. The editor checks registry entries and standard locations. If needed, enter the installation **folder** containing `Plugins`, `scripts` and `x64/TARGETGUI.exe` (or root `TARGETGUI.exe`), then recheck. Official headers remain in that installation.
- [ViGEmBus 1.22.0 release](https://github.com/nefarius/ViGEmBus/releases/tag/v1.22.0): install the signed Windows driver yourself and restart if requested. The project uses the archived ViGEmBus interface; configuration checks an actual client connection, not merely a registry entry.
- [Microsoft Visual C++ x64 runtime](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist): required for the embedded Python and native client. If Python cannot start, install this first. No Microsoft runtime installer is bundled.

The embedded Python and ViGEmClient files are bundled with hashes, origins and license notices in `dependencies/manifest.json`. Emulation refuses a missing or modified bundle. Development tooling and browser automation are separate and are unnecessary for playing.

## Controls and customization

The configuration page includes original schematic diagrams. Numbers are **physical one-based Windows/TARGET button numbers**. Select a diagram marker using mouse, Enter or Space, or use the equivalent labeled control selector. Live highlighting helps locate your actual controls; switch states and lever detents may stay pressed. The diagram is a schematic, not a manufacturer's placement guide. Pilot/Copilot interchangeable button caps may change where a number appears.

- Sidestick 1–4: grip controls; 5–16: base controls. The POV hat is separate from those buttons. Sidestick button 17 (slider/reverse) is not part of the example mapping.
- Quadrant 1–8: switches/buttons. Quadrant 9–16: lever detent states available through TARGET; physical firmware can expose further buttons, which this mapping editor does not assign. No quadrant add-on is required.
- TARGET script button indices start at zero. The UI never asks you to enter those indices. Combined output reserves buttons 1–16 for the stick and 17–32 for quadrant buttons 1–16.

Example presets put roll/pitch on the Xbox left stick or flight keys, twist on yaw, POV on the Xbox right stick or camera keys, and the left lever on acceleration/braking. Stick movement never drives camera movement. Xbox trigger output splits the lever around its neutral band; the high-G button holds both triggers. Set its number to 0 to disable it. Buttons 11–14 are editable wingman placeholders (Xbox D-pad or keyboard F1–F4), based on the requested shared ACE COMBAT 7/8 control scheme; check the actual game's binding screen.

Adjust axis indices, inversion, deadzones, yaw threshold, camera strength, throttle neutral band and polling rate. X/Y/Z/R/U/V are Windows multimedia axes; defaults select X/Y and R twist. TARGET Combined defaults use Z for throttle. The high-G button has priority while held. Other button bindings accept combinations such as `LB+RB` in Xbox modes. Each mode keeps separate mappings. Switching modes asks before discarding unsaved edits. Reset affects the selected mode only.

Keyboard mode has no default QWERTY or AZERTY layout. Any installed Windows layout is selectable. Characters are translated through that layout; **Capture key** stores the physical key and modifier chord instead. Named keys include `Space`, `Tab`, `Enter`, arrow keys, `F1`–`F12` and `Numpad0`–`Numpad9`. Leave a button blank to disable it. Unsupported characters, IME input and ambiguous capture are rejected with an inline error. Match all flight and camera keys to your game's settings; these are editable examples, not a shipped game configuration.

## Startup, stopping and recovery

TARGET starts through its GUI's `-r` option. Startup requires a new per-session readiness signal; TARGET-to-Xbox also requires the expected 4-axis, 32-button Combined controller. Xbox startup verifies a newly available XInput slot. Existing controllers may occupy earlier player slots; games that insist on player 1 may require disconnecting those controllers first.

Stop affects this package's owned session. The bridge neutralizes output and removes its virtual controller, including after a startup failure or disconnect. TARGET acknowledges a private stop request and aborts its own profile. No unrelated TARGET process is killed. If acknowledgement fails, click **Stop** in TARGET and reconnect both devices before retrying. A disconnect is checked every second; keyboard mode also supervises TARGET's readiness heartbeat. A forced process termination, power loss or driver crash can prevent cooperative cleanup; recover in TARGET and reconnect the devices.

If TARGET reports missing HID products you do not own, those excluded devices can be harmless. A filter association error, missing supported controller, failed initialization or timeout is actionable: stop the profile, close TARGET, reconnect the devices directly to the PC, then retry. Do not run multiple TARGET profiles. If Xbox output is absent, recheck ViGEmBus and free an XInput slot. If a game receives duplicate inputs, configure its controller settings or an independently installed device-hiding tool; this project does not install one.

## Files, privacy and redistribution

```text
configure.cmd / emulate.cmd   shared entry points
app/                         single implementation, UI and original TARGET templates
setups/keyboard/              generated standalone keyboard package
setups/xbox/                  generated standalone direct Xbox package
setups/target-xbox/           generated standalone TARGET-to-Xbox package
runtime/                     verified minimal embedded CPython
dependencies/                ViGEmClient, hashes and license notices
tools/                       migration, privacy and release gates
tests/                       unit, browser and boundary tests
.agents/skills/               pinned development skills; not in gamer releases
.local/                      ignored settings, scripts, backups, sessions and reports
```

Private profiles, installation paths and generated TARGET scripts live only under `.local/`. Legacy originals and backups were retained there during migration. `python -m tools.migrate` is a library import workflow; see the developer section for the explicit migration command. Never share `.local/` or a raw desktop-folder archive. Share only an archive built by the release tool. [PRIVACY.md](PRIVACY.md) describes protections and their limits. Original code and diagrams are MIT licensed. Licensed third-party material carries its notices; proprietary TARGET binaries/headers/manuals, game assets and manufacturer artwork are excluded. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Development and verification

Install Python 3.12 and Node.js 26 (development only), then in PowerShell:

```powershell
py -3.12 -m venv .local/dev-venv
.local/dev-venv/Scripts/python.exe -m pip install -r requirements-dev.txt
npm.cmd ci
npx.cmd playwright install chromium
.local/dev-venv/Scripts/python.exe -m pytest -q
npm.cmd test
npm.cmd run test:e2e
.local/dev-venv/Scripts/python.exe -m tools.distribution check
.local/dev-venv/Scripts/python.exe -m tools.distribution packages
.local/dev-venv/Scripts/python.exe -m tools.distribution release
```

Python coverage requires **100% lines and branches** across `app/` and `tools/`. Vitest requires **100% statements, lines, functions and branches** across all first-party UI modules, including unimported files. Tests, third-party skills and generated package copies are not part of those denominators. Boundary doubles exercise Windows devices, process failures, filesystem errors and cleanup; Playwright uses isolated temporary settings and synthetic hardware. A deliberate uncovered-branch test verifies that coverage rejects incomplete code. Reports and traces stay ignored.

These developer commands require the full repository; gamer ZIPs include application source and runtimes while excluding development tooling. `packages` regenerates all standalone copies from the root implementation without overwriting private `.local/` settings. `release` runs Python coverage, JavaScript coverage, browser tests and redistribution/privacy/naming checks before building deterministic allowlisted ZIPs under `.local/releases/`. CI runs the same gates on Windows. Files not explicitly selected cannot enter a release; its file hashes are recorded inside the archive. CI also verifies that standalone copies match their generator.

To import preserved legacy private profiles once:

```powershell
.local/dev-venv/Scripts/python.exe -c "from pathlib import Path; from tools.migrate import migrate; print(migrate(Path.cwd()))"
```

Pinned local skill sources, notices and checksums are documented in [docs/SKILLS.md](docs/SKILLS.md). Product requirements and interface decisions live in [PRODUCT.md](PRODUCT.md) and [DESIGN.md](DESIGN.md). Read [docs/VALIDATION.md](docs/VALIDATION.md) for the distinction between automated checks, actual TARGET compilation/controller checks and gameplay acceptance. Automated tests do not prove physical motion or gameplay behavior.
