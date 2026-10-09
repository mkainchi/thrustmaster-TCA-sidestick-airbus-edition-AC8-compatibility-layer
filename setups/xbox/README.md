# Standalone xbox setup

Run `configure.cmd` to edit xbox mappings, then `emulate.cmd`. Stop with `emulate.cmd --stop`. This directory includes its own runtime and audited dependencies. TARGET and system drivers remain external. Do not move files out of this directory. Private settings live in its ignored `.local/` directory.

# TCA Airbus configuration

Map a Thrustmaster TCA Sidestick Airbus Edition (Pilot or Copilot) and TCA Quadrant Eng 1&2 to keyboard keys or an emulated Xbox controller on Windows x64. The offline browser editor saves a separate profile for each mode.

## Configure, play and stop

1. Connect both devices and run `configure.cmd`.
2. Choose a mode and edit its mappings. Keyboard mode requires an explicit choice of the installed Windows layout used by your game.
3. Open **Dependencies**, install missing prerequisites from the official links, select **Recheck dependencies**, then **Save configuration**.
4. Run `emulate.cmd` before launching the game. Keep its window open.

Stop with `emulate.cmd --stop` or Ctrl+C in the emulation window before editing mappings. Ctrl+C in the configuration command window closes the local editor.

Standalone packages under `setups/` include their own runtime, dependencies and private settings. Their configure command opens the package's mode. Use one package at a time.

## Choose a mode

| Editor label | Command mode | Use | Prerequisites |
| --- | --- | --- | --- |
| Keyboard · TARGET | `keyboard` | Flight, camera and button keys through TARGET | TARGET; Visual C++ x64 runtime |
| Xbox · direct input | `xbox` | Ordinary Xbox-controller play from native joystick input | ViGEmBus; Visual C++ x64 runtime |
| TARGET → Xbox | `target-xbox` | Advanced route through TARGET's Combined controller | TARGET; ViGEmBus; Visual C++ x64 runtime |

Both Xbox modes use the same ViGEmClient/XInput bridge. Choose TARGET → Xbox when your setup needs TARGET to combine the devices first.

## Install prerequisites

- **[TARGET](https://support.thrustmaster.com/en/product/tca-sidestick-airbus-edition-en/):** install it yourself. If automatic detection fails, enter the folder containing `Plugins`, `scripts` and `x64/TARGETGUI.exe` (or root `TARGETGUI.exe`), then recheck.
- **[ViGEmBus 1.22.0](https://github.com/nefarius/ViGEmBus/releases/tag/v1.22.0):** install the signed driver and restart if requested. The project uses this archived interface and checks an actual client connection.
- **[Microsoft Visual C++ x64 runtime](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist):** required by embedded Python and the native client; install it if they cannot start.

Configuration needs no administrator rights; driver installation may. The application never installs drivers or accepts their licenses. Bundled dependencies are verified against `dependencies/manifest.json`; missing or modified files block emulation.

## Edit mappings

Press a hardware button to select its device and binding automatically. Selection pauses while editing a field, capturing a key or saving; the next new press resumes selection. Held switches at connection do not change your selection. You can also choose a control in the selector, select **Edit** in **Mapping overview**, or activate a diagram number with the mouse, Enter or Space. Binding, inline errors and **Save configuration** stay together.

- **Mapping overview** shows outputs by device and keyboard action.
- **Axes and calibration** holds optional input adjustments.
- **Revert to saved** restores the last save after confirmation.
- **Reset this mode** restores example defaults for that mode.

Switching modes asks before discarding unsaved edits.

In Xbox modes, choose an output from the button dropdown. Select **Add button** to build a combination, or **Remove** to clear an output. Choosing **Unassigned** for the last output clears the mapping. LT/RT output full trigger pressure while held; release restores the active throttle's output. High-G keeps priority.

Dropdowns and the keyboard's read-only **Default AC8 PC action** textbox use the **user-supplied AC8 controls** reference. Unlisted keys require manual configuration in game. L3 deploys flares only together with R3; R3 alone changes view. Saved profiles and customized game bindings may differ from the reference; check the game settings.

### Controls and calibration

Stick roll/pitch controls flight, twist controls yaw, and the POV controls the camera. The sidestick slider and quadrant's left lever both control acceleration/braking. Moving either beyond 1% of full travel transfers control immediately to it; the idle throttle is ignored. Both share throttle inversion and center deadzone. The quadrant's right lever is ignored. Xbox output uses the left stick for flight, right stick for camera and triggers for acceleration/braking.

Xbox starts with the quadrant's current position; keyboard output stays neutral until a throttle is moved. High-G release restores the active throttle. If both throttles move in one direct-input sample, the current owner stays active; TARGET processes events in arrival order.

High-G overrides throttle while held; an assigned button binding still fires. Set its number to 0 to disable it. Xbox combinations are saved using `+`, such as `LB+RB`; existing profiles remain compatible.

Calibration adjusts axes, inversion, deadzones, yaw threshold, camera strength, throttle neutral band and input frequency. X/Y/Z/R/U/V are Windows axes; defaults use X/Y and R twist, with Z throttle for TARGET Combined. The sidestick slider uses physical Z/THR; the throttle axis selector configures the quadrant in direct/keyboard modes and the Combined throttle output in TARGET → Xbox.

New/reset profiles assign buttons 11–14 to wingman orders: Xbox D-pad or keyboard Up/Down/Left/Right arrows. Existing saved mappings, including older F1–F4 examples, remain unchanged.

### Keyboard bindings

No QWERTY or AZERTY layout is assumed. Typed characters use the selected layout; **Capture key** stores the physical key and modifier chord instead.

The reference and new/reset profiles use **physical US QWERTY positions**. For example, `KeyQ` is Q's QWERTY position but produces A on French AZERTY: capturing that key or typing `a` with AZERTY selected shows **Yaw left**. Modifiers must match exactly; an added Shift/Ctrl/Alt chord is not assumed to have the same game action.

New/reset keyboard profiles use A/D for roll, W/S for pitch down/up, Q/E for yaw, Space/left Ctrl for acceleration/braking and numpad 8/2/4/6 for camera. Sidestick buttons 1–16 use J, L, K, T, unassigned (High-G), X, V, M, J, unassigned, Up, Down, Left, Right, unassigned, T. Quadrant buttons 1/2 use L/X; other quadrant buttons remain unassigned. START/pause and LB+RB have no single keyboard equivalent in the supplied list, so their keyboard buttons remain unassigned. Reset changes only the current page until you save; it does not overwrite existing profiles automatically.

The reference also includes previous weapon (I), missiles/special weapons (1/2/3), mouse-camera control (F), camera 7/8/9/0 as alternatives to the numpad, autopilot (Z/C), gear (R), view (V), flares (X), target (T) and radar map (M). Mouse alternatives are machine gun (left click), missile/weapon (right click), next/previous weapon (wheel down/up) and target (middle click). These are reference information; keyboard mode emits the keyboard alternatives, not mouse events.

Named keys include `Space`, `Tab`, `Enter`, arrow keys, `PrintScreen`, `F1`–`F24` and `Numpad0`–`Numpad9`. Capture or type standalone modifiers such as `ControlLeft`, `ShiftRight` and `AltLeft`. Standalone modifiers are captured on release; chords complete when their main key is pressed. System/media keys and keys intercepted by Windows or the browser may be unavailable to capture. Leave a button blank to unassign it. Unsupported characters, input-method-editor (IME) input and ambiguous capture receive inline errors.

### Device numbering and diagrams

Match the sidestick diagram's L/R setting to the selector underneath the device. Swappable grip caps may differ from the drawing. Live highlights help verify numbering; switches and detents can stay pressed.

| Device | Controls |
| --- | --- |
| Sidestick | Grip buttons 1–4, base buttons 5–16. POV is separate from button 2. Slider/reverse button 17 is outside this mapping. |
| Quadrant | Switches/buttons 1–8; TARGET lever-detent states 9–16. Further firmware buttons and add-ons are outside this setup. |

The editor uses one-based numbers; it converts TARGET's zero-based script indices. Combined output assigns 1–16 to the stick and 17–32 to quadrant controls 1–16.

Each package includes four original SVG diagrams: sidestick and quadrant top views plus two grip views. They use measured geometry, simplified materials and no manufacturer logos. Official photos/manual crops remain private comparison references; no private image files are needed to configure controls. If a diagram fails to load, use the selector or overview. Official support links provide numbering references. See [artwork terms](THIRD_PARTY_NOTICES.md#private-device-references) and [SVG reconstruction workflow](docs/SKILLS.md#reconstruct-device-svgs).

## Recover from startup or input problems

| Problem | Action |
| --- | --- |
| TARGET filter error, missing supported device, initialization failure or timeout | Stop the profile, close TARGET, reconnect both devices directly to the PC, then retry. Do not run multiple TARGET profiles. |
| Missing TARGET products you do not own | Excluded-device messages can be harmless; check whether supported devices initialize. |
| No Xbox output | Recheck ViGEmBus and free an XInput slot. Disconnect other controllers if the game requires player 1. |
| TARGET does not acknowledge stopping | Select **Stop** in TARGET, reconnect both devices, then retry. |
| Duplicate game input | Check game controller settings or an independently installed device-hiding tool; this project does not install one. |

For startup, disconnect and cleanup behavior, see [Runtime checks](docs/VALIDATION.md#runtime-checks).

## Files, privacy and sharing

Edit the shared implementation in `app/`; regenerate `setups/` through the distribution tool. Each package stores private configuration, scripts, backups, sessions and images under ignored `.local/`.

Share only release-tool archives. Never share `.local/`, the editor URL or a ZIP of the whole project folder. Read [Privacy and sharing](PRIVACY.md) and [Third-party notices](THIRD_PARTY_NOTICES.md).

## Develop and verify

Development requires Python 3.12 and Node.js 26. Gamer packages include their own runtime and need no development tools.

Set up in PowerShell:

```powershell
py -3.12 -m venv .local/dev-venv
.local/dev-venv/Scripts/python.exe -m pip install -r requirements-dev.txt
npm.cmd ci
npx.cmd playwright install chromium
```

After source or documentation changes, regenerate packages and run every check:

```powershell
.local/dev-venv/Scripts/python.exe -m tools.distribution packages
.local/dev-venv/Scripts/python.exe -m pytest -q
npm.cmd test
npm.cmd run test:e2e
.local/dev-venv/Scripts/python.exe -m tools.distribution check
```

Do not edit generated copies. Regeneration preserves private settings. [Validation](docs/VALIDATION.md#automated-checks) defines the 100% coverage gates and separate hardware acceptance.

### Build release archives

```powershell
.local/dev-venv/Scripts/python.exe -m tools.distribution release
```

This repeats acceptance gates and builds deterministic allowlisted ZIPs with file hashes under `.local/releases/`. CI runs the same gates on Windows and checks generated copies.

### Import preserved legacy profiles

Run the library import once:

```powershell
.local/dev-venv/Scripts/python.exe -c "from pathlib import Path; from tools.migrate import migrate; print(migrate(Path.cwd()))"
```

Project context: [requirements](PRODUCT.md), [interface decisions](DESIGN.md), [pinned development skills](docs/SKILLS.md).
