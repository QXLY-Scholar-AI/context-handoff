"""Versioned handoff originals and on-demand inspection; Python standard library only."""
import argparse
import difflib
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def dump(path, value):
    data = json.dumps(value, ensure_ascii=False, indent=2).encode('utf-8')
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_bytes(data)
    temp.replace(path)


def inside(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root) or path == root:
        raise SystemExit('File must be inside the session record directory')
    if path.is_relative_to(root / 'protected-memory'):
        raise SystemExit('Use working handoff files, not protected snapshots')
    return path


def load_revision(vault, number, expected=None):
    folder = vault / f'revision-{number:05}'
    data = (folder / 'manifest.json').read_bytes()
    if expected and sha(data) != expected:
        raise SystemExit('Protected manifest integrity failure')
    manifest = json.loads(data)
    contents = {}
    for row in manifest['files']:
        stored = (folder / row['snapshot']).resolve()
        if not stored.is_relative_to(folder.resolve()):
            raise SystemExit('Invalid protected snapshot path')
        raw = stored.read_bytes()
        if sha(raw) != row['sha256']:
            raise SystemExit('Protected original integrity failure: ' + row['path'])
        contents[row['path']] = raw
    return manifest, contents


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    sub = parser.add_subparsers(dest='action', required=True)
    publish = sub.add_parser('publish')
    publish.add_argument('--files', nargs='+', required=True, help='Paths relative to record root')
    publish.add_argument('--instruction', type=Path, required=True, help='Original user archive approval or correction message')
    publish.add_argument('--basis', choices=['archive-approval', 'user-correction', 'user-confirmation'], required=True)
    inspect = sub.add_parser('inspect')
    inspect.add_argument('--metadata-only', action='store_true')
    restore = sub.add_parser('restore')
    restore.add_argument('--revision', type=int, required=True)
    restore.add_argument('--instruction', type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    vault = root / 'protected-memory'
    pointer_path = vault / 'current.json'
    pointer = json.loads(pointer_path.read_text(encoding='utf-8')) if pointer_path.exists() else None
    previous, old = load_revision(vault, pointer['revision'], pointer['manifest_sha256']) if pointer else (None, {})
    if args.action == 'inspect':
        if not pointer:
            raise SystemExit('No protected original yet; inspect existing handoff and archives before publishing')
        items = []
        for row in previous['files']:
            path = inside(root, row['path'])
            current = path.read_bytes() if path.exists() else None
            item = {**row, 'working_copy_matches': current is not None and sha(current) == row['sha256']}
            if not args.metadata_only:
                item['protected_content'] = old[row['path']].decode('utf-8-sig')
                if not item['working_copy_matches']:
                    item['working_copy_content'] = current.decode('utf-8-sig') if current is not None else None
            items.append(item)
        print(json.dumps({'revision': pointer['revision'], 'created': previous['created'],
                          'basis': previous['basis'], 'instruction': previous['instruction'],
                          'changes': previous['changes'], 'files': items}, ensure_ascii=False, indent=2))
        return
    instruction = args.instruction.read_text(encoding='utf-8-sig').strip()
    if not instruction:
        raise SystemExit('An original user instruction is required')
    if args.action == 'restore':
        if not pointer or args.revision < 1 or args.revision > pointer['revision']:
            raise SystemExit('Unknown revision')
        cursor = pointer
        while cursor['revision'] > args.revision:
            ancestor, _ = load_revision(vault, cursor['revision'], cursor['manifest_sha256'])
            cursor = ancestor['previous']
        selected, contents = load_revision(vault, args.revision, cursor['manifest_sha256'])
        basis = 'user-restore'
    else:
        contents = {}
        for name in args.files:
            path = inside(root, name)
            relative = path.relative_to(root).as_posix()
            raw = path.read_bytes()
            if not raw.strip():
                raise SystemExit('Protected handoff files must be nonempty')
            raw.decode('utf-8-sig')
            contents[relative] = raw
        basis = args.basis
    # Resolve all output paths before any mutation, including restoration paths.
    for name in contents:
        inside(root, name)
    number = pointer['revision'] + 1 if pointer else 1
    target = vault / f'revision-{number:05}'
    target.mkdir(parents=True, exist_ok=False)
    files, changes = [], []
    for index, (name, raw) in enumerate(contents.items(), 1):
        stored = f'{index:03}.txt'
        (target / stored).write_bytes(raw)
        files.append({'path': name, 'snapshot': stored, 'sha256': sha(raw)})
    for name in sorted(set(old) | set(contents)):
        if old.get(name) == contents.get(name):
            continue
        before = old.get(name, b'').decode('utf-8-sig').splitlines()
        after = contents.get(name, b'').decode('utf-8-sig').splitlines()
        changes.append({'path': name, 'diff': '\n'.join(difflib.unified_diff(before, after, fromfile='previous/'+name, tofile='current/'+name, lineterm=''))})
    manifest = {'revision': number, 'previous': pointer, 'created': datetime.now(timezone.utc).isoformat(),
                'basis': basis, 'instruction': instruction, 'files': files, 'changes': changes,
                'confirmation': 'Archive approval permits recording; semantic acceptance only follows an explicit user confirmation or correction.'}
    if args.action == 'restore':
        manifest['restored_from'] = args.revision
        manifest['working_before_restore'] = []
        for name, raw in contents.items():
            path = inside(root, name)
            if path.exists():
                backup = f'working-before-{len(manifest["working_before_restore"])+1:03}.txt'
                current_raw = path.read_bytes()
                (target / backup).write_bytes(current_raw)
                manifest['working_before_restore'].append({'path': name, 'snapshot': backup, 'sha256': sha(current_raw)})
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
    dump(target / 'manifest.json', manifest)
    dump(pointer_path, {'revision': number, 'manifest_sha256': sha((target/'manifest.json').read_bytes())})
    print(json.dumps({'revision': number, 'basis': basis, 'protected_files': list(contents),
                      'changed_files': [r['path'] for r in changes], 'previous_versions_preserved': True}, ensure_ascii=False))


if __name__ == '__main__':
    main()
