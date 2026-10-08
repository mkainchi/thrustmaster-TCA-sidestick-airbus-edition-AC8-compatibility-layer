"""Check shareable repository files without printing private matched values.

Does not inspect device IDs, game saves or Git credentials. Local Git author
name/email may be used as scan markers; their values are never printed or saved.
Use --self-test to test detection without opening the repository.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile

PRIVATE_DIRS = {'.git', '.local', '__pycache__', 'logs', 'diagnostics',
                'screenshots', 'dist', 'releases', 'node_modules', '.venv', '.impeccable',
                'test-results', 'coverage', 'htmlcov', '.pytest_cache', 'playwright-report'}
PRIVATE_SUFFIXES = {'.pyc', '.pyo', '.log', '.dmp', '.sav', '.bak', '.tmp',
                    '.pem', '.key', '.pfx', '.p12'}
RULES = {
    'personal Windows path': re.compile(r'(?i)(?:[a-z]:[\\/]+Users[\\/]+[^\\/\s"<>]+|[a-z]:[\\/]+Documents and Settings[\\/]+[^\\/\s"<>]+)'),
    'personal Unix path': re.compile(r'(?i)/(?:home|Users)/[^/\s"<>]+'),
    'USB instance path': re.compile(r'(?i)USB[\\]+VID_[0-9a-f]{4}&PID_[0-9a-f]{4}[\\]+[^\s"<>]+'),
    'hardware identifier': re.compile(r'(?i)\b(?:serial_number|device_serial|computer_name|hostname|machine_id)\s*[=:]\s*["\'][^"\']+["\']'),
    'private key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'access token': re.compile(r'\b(?:ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[0-9A-Z]{16})\b'),
}


def is_private(path):
    return bool(set(path.parts) & PRIVATE_DIRS) or path.suffix.lower() in PRIVATE_SUFFIXES or path.name.startswith('.env')


def findings(data, private_markers=()):
    texts = (data.decode('utf-8', errors='ignore'),
             data.decode('utf-16-le', errors='ignore'),
             data.decode('utf-16-be', errors='ignore'))
    hits = {label for label, rule in RULES.items() if any(rule.search(t) for t in texts)}
    for marker in private_markers:
        if marker and any(re.search(r'(?<![a-z0-9])' + re.escape(marker) + r'(?![a-z0-9])', t, re.I) for t in texts):
            hits.add('current user identity/path')
    return sorted(hits)


def inventory(root):
    # Use Git's exclusion rules, including additional user-defined ignores.
    result = subprocess.run(['git', '-C', str(root), 'ls-files', '-z', '--cached',
                             '--others', '--exclude-standard'], capture_output=True)
    if result.returncode:
        raise RuntimeError('Git inventory unavailable. Run this check inside the repository.')
    return sorted(set(Path(os.fsdecode(p)) for p in result.stdout.split(b'\0') if p))


def audit(root, extra_markers=(), paths=None):
    home = Path.home()
    # The name is detected locally and never saved to a report or printed.
    username = home.name if len(home.name) >= 3 else ''
    git_identity = []
    for setting in ('user.name', 'user.email'):
        result = subprocess.run(['git','-C',str(root),'config','--get',setting],capture_output=True)
        value = result.stdout.decode('utf-8',errors='ignore').strip()
        if result.returncode == 0 and len(value) >= 3:
            git_identity.append(value)
    markers = (str(home), home.as_posix(), username, *git_identity, *extra_markers)
    allowlist_path = root / 'tools' / 'privacy_upstream.json'
    allowlist = json.loads(allowlist_path.read_text(encoding='utf-8')) if allowlist_path.exists() else {}
    issues = []
    for relative in inventory(root) if paths is None else paths:
        path = root / relative
        if is_private(relative):
            issues.append((relative, 'private file included in Git inventory'))
            continue
        if path.is_symlink():
            issues.append((relative, 'symlink could expose external files'))
            continue
        if not path.is_file():
            continue
        data = path.read_bytes()
        hits = set(findings(data, markers)) | set(findings(relative.as_posix().encode(), markers))
        if path.suffix.lower() == '.zip':
            try:
                with zipfile.ZipFile(path) as archive:
                    if sum(entry.file_size for entry in archive.infolist()) > 256_000_000:
                        hits.add('archive too large for privacy inspection')
                    else:
                        for entry in archive.infolist():
                            hits.update(findings(entry.filename.encode(), markers))
                            hits.update(findings(archive.read(entry), markers))
            except (OSError, ValueError, RuntimeError, zipfile.BadZipFile):
                hits.add('unreadable archive')
        approved = allowlist.get(relative.as_posix(), {})
        if len(relative.parts) > 2 and relative.parts[0] == 'setups' and relative.parts[1] in ('keyboard', 'xbox', 'target-xbox'):
            approved = allowlist.get(Path(*relative.parts[2:]).as_posix(), approved)
        if approved.get('sha256') == hashlib.sha256(data).hexdigest():
            # Only confirmed upstream path examples/build metadata may be
            # exempted. Never exempt current identity, credentials or USB IDs.
            permitted = {'personal Windows path', 'personal Unix path'}
            hits -= set(approved.get('categories', [])) & permitted
        for label in sorted(hits):
            issues.append((relative, label))
    return issues


def safe_label(path):
    # Don't print a user-supplied filename that itself contains private data.
    return '/'.join('[private]' if findings(p.encode(), (Path.home().name,)) else p
                    for p in path.parts)


def self_test():
    personal = 'C:' + chr(92) + 'Users' + chr(92) + 'ExamplePrivateUser' + chr(92) + 'Desktop'
    instance = 'USB' + chr(92) + 'VID_044F&PID_0405' + chr(92) + 'ExampleInstance'
    assert 'personal Windows path' in findings(personal.encode())
    assert 'personal Windows path' in findings(personal.encode('utf-16-le'))
    assert 'USB instance path' in findings(instance.encode())
    assert not findings(b'Generic supported products: T.A320 Pilot; TCA Q-Eng 1&2')
    assert is_private(Path('setup/.local/profile.json'))
    assert is_private(Path('setup/vendor/__pycache__/module.pyc'))
    assert not is_private(Path('setup/runtime/python314.zip'))
    assert findings(b'ExamplePrivateUser', ('ExamplePrivateUser',))
    print('Privacy detector self-tests passed.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    issues = audit(args.root.resolve())
    for relative, label in issues:
        print(f'{safe_label(relative)}: {label}')
    print(f'Privacy check: {len(issues)} issue(s). Matched private values are never printed.')
    return 1 if issues else 0


if __name__ == '__main__':
    raise SystemExit(main())
