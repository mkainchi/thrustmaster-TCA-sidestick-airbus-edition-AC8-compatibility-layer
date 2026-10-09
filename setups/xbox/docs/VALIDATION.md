# Validation and hardware acceptance

Automated checks verify software behavior; physical checks verify controllers and gameplay. Coverage means lines and branches were exercised, not that a game works correctly.

## Automated checks

Run every command in [Develop and verify](../README.md#develop-and-verify).

| Check | Scope |
| --- | --- |
| pytest | All first-party Python in `app/` and `tools/`, including unimported modules; 100% lines and branches, no coverage-ignore directives |
| Vitest | All first-party application/tool JavaScript, including boot, configuration and unimported modules; 100% statements, lines, functions and branches |
| Negative coverage probes | Missing branches and unimported modules must fail the gates |
| Playwright | Real local server, isolated settings, synthetic controller/dependency data and shipped SVG assets |
| Release and Windows CI | Coverage, browser, naming, privacy and license gates before allowlisted packaging |

Unit boundaries exercise Windows APIs, profiles, translation, migration, atomic saves, dependencies, session ownership, throttle takeover/noise/High-G, startup, disconnects and cleanup failures. Browser scenarios check mode/layout consent, independent mappings, capture, physical-button selection, editing/held-switch protections, optional calibration, overlays/overview, unsaved edits, save/load/dependency recovery, request protections, contrast, focus and reflow.

Synthetic input and rendered diagrams do not prove hardware behavior. Development skills, private reports and browser binaries are excluded from releases.

## Runtime checks

- TARGET starts through its GUI's `-r` option. Each session requires fresh readiness; TARGET → Xbox also requires a Combined controller with 4 axes and 32 buttons.
- Xbox startup verifies a new XInput slot. Other controllers can occupy earlier player slots.
- Stop affects only the package's owned session. The bridge neutralizes output and removes its virtual controller after stopping, startup failure or disconnect.
- TARGET acknowledges a private stop request and aborts its own profile; unrelated TARGET processes are not killed. If acknowledgement fails, select **Stop** in TARGET and reconnect both devices.
- Disconnects are checked every second; keyboard mode also monitors TARGET's readiness heartbeat.
- Forced termination, power loss or driver failure can prevent cooperative cleanup. Stop the profile in TARGET and reconnect the devices.

## Device diagram inspection

Four original SVG diagrams were rendered and visually compared against private `sidestick.png`, `quadrant.png`, `sidestick-grip.png` and `quadrant-grip.png` references using Pixel2Motion's overlay workflow. Check silhouette, proportions, control centers and enlarged smooth edges. Logos, photographic texture, manual annotations and hands are deliberately omitted; numbers remain interactive HTML overlays.

Preserve sidestick L/R numbering, grip buttons 1/2 separate from POV, quadrant shared selector 7/8 and TARGET detent states 9–16. Server/browser checks confirm that all four SVGs load without private images and that unauthorized asset paths stay inaccessible.

Visual agreement does not prove firmware numbering or live highlights. Keep source URLs, hashes and notes in ignored `.local/`; perform the physical checks below.

## Recorded implementation checks

These results describe checks already performed. They do not replace a fresh hardware acceptance run.

| Check | Result | Limit |
| --- | --- | --- |
| Official CPython archive SHA-256 and retained-file equality | Passed | The local `_pth` file is intentionally authored; every retained upstream binary/stdlib/notice is unchanged. |
| ViGEmClient DLL equality with pinned vgamepad source archive | Passed | Pins the exact binary origin rather than guessing its internal build version. |
| Installed TARGET Interpreter offline `ValidateProfile` for generated keyboard and Combined templates | Passed | Runs pure validation, without Init, hardware capture or output. Official headers were used only in ignored temporary compilation storage. |
| Shared throttle ownership and keyboard state replay in installed TARGET Interpreter | Passed | Generated Pilot/Copilot keyboard and Combined profiles compile and pass pure replay; no directed physical input or game output is proven. |
| Native WinMM input from both supported physical devices | Passed | Presence/neutral state read; no directed button/axis motion test was performed. |
| Actual ViGEmBus virtual Xbox allocation, neutral report, XInput visibility and removal | Passed | Driver/output lifecycle check; not a game or movement check. |
| Actual TARGET GUI `-r`, fresh readiness, Combined descriptor and cooperative stop | Incomplete | An initial profile wrote readiness and acknowledged stop, but its descriptor was unavailable to the bridge. Later GUI runs exited without readiness. The application refused startup and retained actionable recovery state. Stop TARGET and reconnect both devices before retrying this check. |
| Physical movement, keyboard output and gameplay | Not performed | Requires directed input and an installed game. Do not claim gameplay acceptance from unit tests. |

## Physical acceptance

### 1. Prepare

Stop emulation and TARGET profiles. Reconnect both devices directly to the PC, confirm them in Windows Game Controllers, then run `configure.cmd` and recheck dependencies.

### 2. Check direct Xbox motion

Confirm a new Windows/XInput Xbox controller, then verify:

- Stick movement changes the left stick while the right stays centered.
- Twist changes yaw; POV changes only right stick/camera.
- Move the quadrant's left lever, then the sidestick slider: each must produce the same acceleration/braking direction and center neutral behavior.
- Move the inactive throttle beyond 1% of full travel: it must take over immediately. Slow accumulated movement must also take over; minor jitter must not. The quadrant's right lever must have no throttle effect.
- High-G overrides throttle while held; switch throttles while holding it, then verify release restores the most recently active throttle.

### 3. Check physical numbering

Compare each physical control with its live diagram highlight, including switches/detents and assigned/unassigned wingman buttons. Record firmware differences privately; do not publish unique hardware IDs.

Check normal button taps select the exact button and device. Keep a switch held while reconnecting: it must not change selection until a new press. Type a binding or capture a key while pressing hardware buttons; selection, focus and edits must stay stable until a subsequent new press after editing ends. Click both device tabs and numbered buttons to verify manual selection.

### 4. Check keyboard output

Use a temporary text/key monitor. Explicitly select each layout used for play and check characters, physical capture and modifiers. Verify held/released flight, POV camera, throttle and High-G keys.

After READY, keyboard throttle output must remain neutral until either throttle moves meaningfully. Repeat handoff, neutral, jitter and High-G checks using a key monitor.

### 5. Check TARGET → Xbox and disconnect recovery

Wait for READY, confirm 4 axes/32 buttons, and repeat motion checks on the new Xbox controller. Unplug a physical device while holding a control: output must become neutral and the virtual controller disappear. Reconnect and restart.

### 6. Check both stopping methods

Test `emulate.cmd --stop` and Ctrl+C separately. Verify key release, Xbox removal, TARGET acknowledgement and restored physical controllers. Check failure recovery without killing unrelated TARGET processes.

### 7. Check gameplay

Verify controller/player assignment, bindings, roll, pitch, yaw, throttle, camera, weapons and wingman actions. Check expert/standard flight preferences and deadzone/inversion changes. Keyboard examples must match the game's options.

Keep screenshots, generated profiles, logs and hardware notes in `.local/`. Filter errors and timeouts are failed checks: resolve them through TARGET's Stop/reconnect workflow before claiming readiness.
