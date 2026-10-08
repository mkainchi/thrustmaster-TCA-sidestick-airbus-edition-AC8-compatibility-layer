# Validation and hardware acceptance

Automated checks and physical/gameplay checks answer different questions. A 100% coverage gate proves that the instrumented lines and branches were exercised; assertions and boundary simulations still determine whether those exercises are meaningful. Neither coverage nor browser fixtures prove flight behavior in a game.

## Automated acceptance

- pytest measures all first-party Python in app/ and tools/, including unimported modules: 100% line and branch thresholds, no coverage-ignore directives.
- Vitest measures all first-party application/tool JavaScript: 100% statements, lines, functions and branches. Boot and configuration modules are exercised as well as UI logic.
- Dedicated negative probes confirm that a missing branch and an unimported module fail each coverage gate.
- Unit boundaries cover installed layouts/translation, profiles/migration, atomic saves and failure preservation, dependency detection/integrity, single owned sessions, TARGET readiness/heartbeat, XInput readiness, disconnects, neutral output, stop acknowledgement and cleanup failures.
- Playwright launches the real local server with isolated temporary settings and synthetic controller/dependency data. Eleven scenarios cover all three modes, first-run consent, mode persistence/independent mappings, calibration, capture, diagrams, unsaved changes, dependency rechecking, failed saves/loading, local-only requests, cross-origin rejection, contrast, keyboard focus and narrow layouts.
- The release command runs both coverage gates, browser tests and naming/privacy/license checks before building allowlisted archives. CI repeats those gates on Windows. The development skills, private reports and browser binaries do not enter archives.

## Actual checks performed during implementation

| Check | Result | Limit |
| --- | --- | --- |
| Official CPython archive SHA-256 and retained-file equality | Passed | The local `_pth` file is intentionally authored; every retained upstream binary/stdlib/notice is unchanged. |
| ViGEmClient DLL equality with pinned vgamepad source archive | Passed | Pins the exact binary origin rather than guessing its internal build version. |
| Installed TARGET Interpreter offline `ValidateProfile` for generated keyboard and Combined templates | Passed | Runs pure validation, without Init, hardware capture or output. Official headers were used only in ignored temporary compilation storage. |
| Native WinMM input from both supported physical devices | Passed | Presence/neutral state read; no directed button/axis motion test was performed. |
| Actual ViGEmBus virtual Xbox allocation, neutral report, XInput visibility and removal | Passed | Driver/output lifecycle check; not a game or movement check. |
| Actual TARGET GUI `-r`, fresh readiness, Combined descriptor and cooperative stop | Incomplete | An initial profile wrote readiness and acknowledged stop, but its descriptor was unavailable to the bridge. Later GUI runs exited without readiness. The application refused startup and retained actionable recovery state. Stop TARGET and reconnect both devices before retrying this check. |
| Physical movement, keyboard output and gameplay | Not performed | Requires directed input and an installed game. Do not claim gameplay acceptance from unit tests. |

## Physical acceptance checklist

1. Stop all emulation/TARGET profiles. Reconnect both TCA devices directly to the PC. Confirm the expected devices in Windows Game Controllers. Recheck dependencies in configure.cmd.
2. Test direct Xbox first. Confirm a new Xbox controller in Windows/XInput. Move the stick in each direction: left stick changes, right stick stays centered. Twist changes yaw. POV changes right stick/camera only. Move the left lever across neutral; acceleration/braking changes and neutral releases both. Verify high-G and its release restore the lever's requested state.
3. Press each diagram number and compare live highlights with actual physical numbering, including switches/detents. Record firmware-specific differences only in private notes; do not publish unique hardware identifiers. Check assigned/unassigned wingman buttons.
4. Test keyboard mode with a temporary text/key monitor. Explicitly select each installed layout used for play; check characters, physical capture and modifiers. Check held/released flight keys, camera POV, throttle and high-G. Move the left lever once after READY to establish its initial keyboard zone.
5. Test TARGET-to-Xbox: wait for READY, verify the Combined descriptor (4 axes, 32 buttons), repeat movement checks and inspect the new Xbox controller. Unplug one physical device while a control is held; verify output is neutral and the controller is removed. Reconnect and restart.
6. Stop with emulate.cmd --stop and Ctrl+C separately. Verify keyboard releases, Xbox removal, TARGET stop acknowledgement and restored physical controllers. Test failure recovery without killing unrelated TARGET processes.
7. In the game, check controller/player assignment and game bindings. Confirm roll, pitch, yaw, throttle, camera, weapons and wingman actions. Test expert/standard flight-control preferences and deadzone/inversion changes. Keyboard bindings are editable examples and must match the game's options.

Keep screenshots, generated profiles, driver logs and detailed physical test notes in .local/. A filter association error or timeout is not a passing hardware check. Resolve it through TARGET's Stop/reconnect workflow before claiming readiness.
