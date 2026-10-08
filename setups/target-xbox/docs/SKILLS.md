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
| [Pixel2Motion](https://github.com/nolangz/pixel2motion) | pixel2motion | e9faedb28930df0da2acf17da00c80730a78cfe8 | MIT; copyright Nolan Lai retained |

## Reconstruct device SVGs

Use Pixel2Motion's source analysis and static vector phases for `sidestick`, `quadrant`, `sidestick-grip` and `quadrant-grip`. The source PNGs remain private in `.local/device-images/`. The main SVGs retain `viewBox="0 0 1920 1080"`; grip views retain 152×125 and 145×115, keeping numbered overlays aligned.

Draw original geometry with primitives, smooth paths and semantic groups. Omit logos, embedded rasters, scripts, external resources and animation. Render each SVG, inspect source/overlay/vector comparisons and zoomed edges, and document deliberate simplifications. Use the pinned `render_overlay.py`, `svg_path_audit.py` and `overlay_progress_strip.py`; keep fitting scripts, metrics and evidence under ignored `.local/`. For photographic sources, distinguish the gallery background from device material before interpreting silhouette overlap. Line-art overlap also counts omitted annotations and line weight, so inspect control positions separately.

The four SVGs in `app/web/device/` are application assets. Regenerate packages through `tools.distribution` after changing them.

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
