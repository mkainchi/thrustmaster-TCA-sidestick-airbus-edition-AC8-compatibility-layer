# Third-party notices and redistribution

Original application code, documentation and original SVG schematics are licensed under the root MIT LICENSE. Trademarks remain their owners' property. Third-party dependencies retain their licenses and copyright notices; licensed copyrighted open-source material is permitted. No proprietary TARGET headers/binaries/manuals, game assets or manufacturer artwork are shipped.

## Gamer bundle

Exact retained-file SHA-256 values, versions, origins and notice locations are in `dependencies/manifest.json`. The release gate verifies them byte-for-byte before packaging.

| Component | Version and origin | License and included notice | Redistribution handling |
| --- | --- | --- | --- |
| CPython Windows x64 embedded subset | 3.14.5, official [embedded archive](https://www.python.org/ftp/python/3.14.5/python-3.14.5-embed-amd64.zip) | PSF-2.0 and historical/embedded licenses, `runtime/LICENSE.txt` and `dependencies/licenses/cpython-LICENSE.txt` | Retained files compared with the SHA-256 pinned official archive. Only `python314._pth` is locally changed to load adjacent application source. Full upstream notice is retained. |
| libffi, used by `_ctypes` | 3.4.4, CPython's pinned [build property](https://github.com/python/cpython/blob/v3.14.5/PCbuild/python.props) | MIT, `dependencies/licenses/libffi-LICENSE.txt` | Official embedded `libffi-8.dll` retained without changes. |
| zlib-ng, built into Python | 2.2.4, CPython's pinned build properties and [upstream release](https://github.com/zlib-ng/zlib-ng/tree/2.2.4) | Zlib and accompanying upstream notices, `dependencies/licenses/zlib-ng-LICENSE.md` | Complete upstream notice retained; Python's linked compression code is covered. |
| ViGEmClient x64 DLL | Exact DLL from the SHA-256 pinned [vgamepad 0.1.0 source archive](https://pypi.org/project/vgamepad/0.1.0/) | MIT, `dependencies/licenses/vigemclient-LICENSE.txt` | DLL compared byte-for-byte with the pinned archive. No vgamepad Python wrappers or installers are bundled. Keyboard-only packages omit this client. |

The embedded CPython LICENSE includes notices applicable to Python's historical code, built-in HACL* hashing and other upstream components. Unused optional modules and native DLLs (including OpenSSL, SQLite and compression extensions) are not retained. The binary and standard-library files remain upstream originals. The permissive licenses retained above do not impose a corresponding-source delivery requirement; exact source/build origins are recorded for inspection. There are no LGPL pygame/SDL binaries in this release.

## External prerequisites

TARGET and official device drivers remain external proprietary prerequisites, obtained from [Thrustmaster support](https://support.thrustmaster.com/en/product/tca-sidestick-airbus-edition-en/). Official TARGET script headers are read only from the user's installation and are not copied into the repository or release. TARGET templates in app/templates are original application scripts.

ViGEmBus is an external signed driver from its [official release](https://github.com/nefarius/ViGEmBus/releases/tag/v1.22.0). Its installer and driver binaries are not bundled. Microsoft Visual C++ x64 runtime DLLs/installers are also excluded; install them from [Microsoft](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist). This avoids unresolved Microsoft redistribution entitlement. Configuration provides links and checks health but never installs drivers or accepts external licenses automatically.

## Development material

Project-local skills are pinned in `.agents/skills.lock.json`. Every skill includes its upstream LICENSE. Impeccable additionally retains its Apache-2.0 NOTICE.md; Ponytail's main/audit/review and the other selected development skills retain MIT notices. See docs/SKILLS.md for exact repositories/commits. The private verified Impeccable engine is excluded from redistribution.

pytest, coverage, Vitest, jsdom, Playwright and Chromium are downloaded development dependencies, with pinned direct versions and npm's lockfile. They are not vendored in gamer packages; their notices remain in the development environment. No downloaded browser, npm node_modules or Python development environment enters an archive.

Adding any native dependency requires a new origin/hash/license audit and notice update. Unknown redistribution permission is a release blocker: keep that component external until verified. The allowlist cannot automatically infer permission from a top-level package license.
