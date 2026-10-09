"""Hash/license/naming/privacy gates and deterministic standalone packages."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile
from app.model import MODES
from tools.privacy_check import audit, inventory, safe_label

DOCUMENTS = {'README.md', 'LICENSE', 'PRIVACY.md', 'THIRD_PARTY_NOTICES.md', 'AGENTS.md',
             'SKILL.md', 'PRODUCT.md', 'DESIGN.md', 'SKILLS.md', 'VALIDATION.md'}
ROOT_FILES = ('README.md', 'LICENSE', 'PRIVACY.md', 'THIRD_PARTY_NOTICES.md', 'PRODUCT.md', 'DESIGN.md', 'configure.cmd', 'emulate.cmd')
APP_FILES = tuple('app/' + name for name in ('__init__.py', '__main__.py', 'cli.py', 'dependencies.py', 'keyboard.py',
    'model.py', 'server.py', 'session.py', 'target.py', 'windows.py', 'templates/keyboard.tmc', 'templates/target-xbox.tmc', 'templates/throttle.tmh',
    'web/index.html', 'web/boot.js', 'web/ui.js', 'web/logic.js', 'web/style.css',
    'web/device/sidestick.svg', 'web/device/quadrant.svg', 'web/device/sidestick-grip.svg', 'web/device/quadrant-grip.svg'))
DOC_FILES = ('docs/SKILLS.md', 'docs/VALIDATION.md')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_relative(name):
    path = Path(name)
    if path.drive or path.root or '..' in path.parts or '\\' in name or not path.parts:
        raise ValueError('Unsafe dependency manifest path.')
    return path


def locked_files(root):
    manifest = json.loads((root / 'dependencies/manifest.json').read_text())
    if manifest.get('version') != 1 or not manifest.get('files') or not manifest.get('components'):
        raise ValueError('Invalid dependency manifest.')
    for name, checksum in manifest['files'].items():
        path = safe_relative(name)
        if path.parts[0] not in ('runtime', 'dependencies') or not re.fullmatch('[a-f0-9]{64}', checksum):
            raise ValueError('Invalid dependency checksum entry.')
        if not (root / path).is_file() or (root / path).is_symlink() or digest(root / path) != checksum:
            raise ValueError('A bundled dependency is missing or modified.')
    covered = set()
    for component in manifest['components']:
        if component.get('license') not in ('PSF-2.0', 'MIT', 'Zlib') or not component.get('origin', '').startswith('https://') or not component.get('version'):
            raise ValueError('Unresolved dependency redistribution permission or origin.')
        if component.get('notice') not in manifest['files']:
            raise ValueError('A required dependency notice is missing.')
        files = component.get('files', [])
        if not files or component['notice'] not in files or any(name not in manifest['files'] for name in files):
            raise ValueError('Dependency license coverage is incomplete.')
        covered.update(files)
    if covered != set(manifest['files']):
        raise ValueError('An unlicensed dependency file is present.')
    return manifest


def skill_files(root):
    locked = set()
    for skill in json.loads((root / '.agents/skills.lock.json').read_text()):
        if not re.fullmatch('[a-f0-9]{40}', skill['commit']) or skill['license'] not in ('MIT', 'Apache-2.0') or 'LICENSE' not in skill['files']:
            raise ValueError('Unverified skill provenance or license.')
        if skill['license'] == 'Apache-2.0' and 'NOTICE.md' not in skill['files']:
            raise ValueError('Apache skill attribution notice is missing.')
        base = Path('.agents/skills') / safe_relative(skill['name'])
        for name, checksum in skill['files'].items():
            path = base / safe_relative(name)
            if (root / path).is_symlink() or not (root / path).is_file() or digest(root / path) != checksum:
                raise ValueError('A pinned skill file is missing or modified.')
            locked.add(path)
    return locked


def check(root, verify_packages=True):
    manifest = locked_files(root)
    upstream = set(map(Path, manifest['files'])) | skill_files(root)
    paths = sorted(set(inventory(root)) | set(map(Path, (*ROOT_FILES, *APP_FILES, *DOC_FILES))))
    for path in paths:
        relative = path
        if len(path.parts) > 2 and path.parts[0] == 'setups' and path.parts[1] in MODES:
            relative = Path(*path.parts[2:])
        if relative in upstream:
            continue
        if relative.suffix.lower() in ('.exe', '.dll', '.pyd', '.zip'):
            raise ValueError('An unverified public binary is present.')
        if any(part != part.lower() and part not in DOCUMENTS for part in relative.parts):
            raise ValueError('Unexpected filename casing: ' + safe_label(path))
    if audit(root, paths=paths):
        raise ValueError('Privacy check failed. Run check_privacy.cmd for redacted finding categories.')
    if verify_packages:
        for mode in MODES:
            folder = root / 'setups' / mode
            if folder.exists():
                for name, data in payload(root, mode).items():
                    if not (folder / name).is_file() or (folder / name).read_bytes() != data:
                        raise ValueError('Standalone packages are stale. Regenerate using distribution packages.')
    return manifest


def payload(root, mode=None):
    manifest = locked_files(root)
    files = {name: (root / name).read_bytes() for name in ROOT_FILES}
    for name in APP_FILES:
        files[name] = (root / name).read_bytes()
    for name in manifest['files']:
        files[name] = (root / name).read_bytes()
    if mode == 'keyboard':
        manifest = json.loads(json.dumps(manifest))
        for name in next(item['files'] for item in manifest['components'] if item['name'] == 'vigemclient'):
            del files[name]
            del manifest['files'][name]
        manifest['components'] = [item for item in manifest['components'] if item['name'] != 'vigemclient']
    files['dependencies/manifest.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
    for name in DOC_FILES:
        files[name] = (root / name).read_bytes()
    if mode is not None:
        for command in ('configure', 'emulate'):
            files[command + '.cmd'] = (f'@echo off\r\nsetlocal\r\n"%~dp0runtime\\python.exe" -B -m app {command} --mode {mode} %*\r\nexit /b %errorlevel%\r\n').encode()
        files['README.md'] = (f'# Standalone {mode} setup\n\nRun `configure.cmd` to edit {mode} mappings, then `emulate.cmd`. Stop with `emulate.cmd --stop`. This directory includes its own runtime and audited dependencies. TARGET and system drivers remain external. Do not move files out of this directory. Private settings live in its ignored `.local/` directory.\n\n' + files['README.md'].decode()).encode()
    files['.gitignore'] = b'.local/\n__pycache__/\n*.pyc\n'
    files['release-files.json'] = (json.dumps({name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())}, indent=2) + '\n').encode()
    return files


def packages(root):
    check(root, verify_packages=False)
    for mode in MODES:
        folder = root / 'setups' / mode
        for name, data in payload(root, mode).items():
            path = folder / safe_relative(name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    check(root)


def release(root, runner=subprocess.run):
    # Run every acceptance gate before producing even the first archive.
    for command in ([sys.executable, '-m', 'pytest', '-q'], ['npm.cmd', 'test'], ['npm.cmd', 'run', 'test:e2e']):
        runner(command, cwd=root, check=True)
    check(root)
    output = root / '.local/releases'
    output.mkdir(parents=True, exist_ok=True)
    built = []
    for mode in (None, *MODES):
        name = 'tca-config-windows-x64' if mode is None else 'tca-' + mode + '-windows-x64'
        archive = output / (name + '.zip')
        temporary = archive.with_suffix('.tmp')
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED) as stream:
            for path, data in sorted(payload(root, mode).items()):
                info = zipfile.ZipInfo(path, date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                stream.writestr(info, data)
        temporary.replace(archive)
        archive.with_suffix('.sha256').write_text(digest(archive) + '  ' + archive.name + '\n')
        built.append(archive)
    return built


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('check', 'packages', 'release'))
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    try:
        {'check': check, 'packages': packages, 'release': release}[args.command](args.root.resolve())
        print('Distribution ' + args.command + ': passed.')
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError):
        print('Distribution gate failed. Check dependency locks, naming, privacy and test output.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
