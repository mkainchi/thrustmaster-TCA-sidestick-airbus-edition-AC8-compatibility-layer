# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Windows x64 gamers using a TCA Sidestick Airbus Edition and TCA Quadrant Eng 1&2. They clone or extract the project, choose a mode, customize controls and start emulation.

## Product Purpose

Provide keyboard through TARGET, direct Xbox emulation, and TARGET-to-Xbox emulation with one offline configuration page and two command entry points. Success means a user can identify physical controls, configure a preferred mode, resolve prerequisites and start and stop a verified session.

## Operating Context

The configuration page runs on loopback. TARGET and required system drivers are installed separately. Example ACE COMBAT controls are editable and must be checked in the game's settings. Physical joystick motion controls flight; the POV controls the camera.

## Capabilities and Constraints

Use plain HTML, CSS and JavaScript with Python. Keep per-mode profiles independent. Require explicit selection of an installed keyboard layout in keyboard mode, without a French or English default. No telemetry, personal hardware inventory, automatic driver installation, proprietary software, copied game assets or manufacturer artwork. Distribute only verified licensed dependencies.

## Evidence on Hand

Existing keyboard translation, local editor protections, TARGET templates and Xbox input mapping. Automated tests are evidence of software behavior; hardware motion and gameplay require separate checks.

## Product Principles

- Make physical-to-virtual mappings visible and editable.
- Preserve local choices and provide actionable dependency errors.
- Release held controls when stopping or losing input.
- Keep personal configuration and diagnostics private.

## Accessibility & Inclusion

Configuration must work using a keyboard, support zoom and narrow windows, label every control and expose errors and status changes to assistive technology.
