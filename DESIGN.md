# Configuration interface

Use Impeccable's Operate mode: familiar controls and a direct path from mode choice to saved mappings.

## Editing flow

- Show relevant prerequisites with nearby remedies.
- Keep control selection, binding, inline error and Save together.
- Synchronize live button presses, the native selector and diagram selection without moving focus or losing edits. Pause automatic selection while editing, capturing a key or saving, and resume on the next new press.
- Offer an editable overview grouped by device and keyboard actions, with explicit High-G behavior.
- Keep calibration optional.
- Distinguish loading, unavailable input, unsaved changes, saving, success and failure. Associate errors with fields and summarize them in a live status region.

## Device references

Place numbered original SVG diagrams beside the editor. Draw measured device geometry from private photo/manual references, preserving proportions, visible controls and grip views. Ship self-contained vectors in `app/web/device/`; omit embedded rasters, logos and external requests. Keep the selector and overview usable if a diagram fails to load.

Follow official mapping diagrams, including L/R sidestick numbering and separate grip views. Distinguish feature callouts, physical buttons, POV and virtual detents.

## Visual language and accessibility

Use native controls, a restrained dark workspace, system fonts, one accent and semantic color tokens.

On narrow windows, put editing before optional diagrams. Preserve 44px targets in labeled scrolling regions and usable focus/controls at 200% zoom. Avoid decorative animation, external fonts and external runtime assets.
