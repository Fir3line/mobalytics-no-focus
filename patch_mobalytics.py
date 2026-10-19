"""Reversible, version-pinned Mobalytics focus patch. Standard library only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import time

ROOT = Path(__file__).resolve().parent / '.backups'
INSTALL = Path(os.environ.get('LOCALAPPDATA', '.')) / 'Programs/mobalytics-desktop'
EXE = INSTALL / 'Mobalytics.exe'
ASAR = INSTALL / 'resources/app.asar'
ORIGINAL_HEADER = 'fd3bfb6457d5b0a44bcbe1086511e1c9d14cc5e90dd6b858a39e7f489ebd80ac'
PATCHED_HEADER = 'ad90428901fc8d74a064dd1104601465e9686ef1295c01d51ca55110f6099915'
PATTERN = re.compile(rb'this\.windowsManagerService\.(?:bringToFront|restore|showWindowBehind)\([^;\r\n]*\);')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def archive_info(path):
    with path.open('rb') as f:
        prefix = f.read(16)
        _, header_size, _, json_size = struct.unpack('<4I', prefix)
        raw = f.read(json_size)
        header = json.loads(raw)
        entry = header['files']['build']['files']['src_lol_bootstrap_ts.js']
        offset = 8 + header_size + int(entry['offset'])
        f.seek(offset)
        content = f.read(entry['size'])
    if len(content) != entry['size'] or digest(content) != entry['integrity']['hash']:
        raise RuntimeError('Archive entry failed integrity validation.')
    return raw, entry, offset, content


def plan():
    original_asar = ROOT / 'app.asar.original'
    original_exe = ROOT / 'Mobalytics.exe.original'
    raw, entry, offset, content = archive_info(original_asar)
    if digest(raw) != ORIGINAL_HEADER:
        raise RuntimeError('Original backup is not the supported version.')
    start = content.index(b'    async updateLCWindow(placeBehindGame = true) {')
    end = content.index(b'    async reset() {', start)
    section = content[start:end]
    if len(PATTERN.findall(section)) != 13:
        raise RuntimeError('Unexpected activation code; refusing to patch.')
    fixed = PATTERN.sub(lambda m: b'void 0;'.ljust(len(m.group())), section)
    patched = content[:start] + fixed + content[end:]
    if len(patched) != len(content):
        raise RuntimeError('Patch changed entry size.')
    if len(entry['integrity']['blocks']) != 1:
        raise RuntimeError('Unsupported archive integrity layout.')
    new_raw = raw.replace(entry['integrity']['hash'].encode(), digest(patched).encode())
    if digest(new_raw) != PATCHED_HEADER or len(new_raw) != len(raw):
        raise RuntimeError('Patch result differs from the validated patch.')
    if file_hash(original_asar) != SUPPORTED['original_asar_sha256'] or file_hash(original_exe) != SUPPORTED['original_exe_sha256']:
        raise RuntimeError('Original backups do not match the reviewed release.')
    original_binary = original_exe.read_bytes()
    if original_binary.count(ORIGINAL_HEADER.encode()) != 1:
        raise RuntimeError('Expected executable metadata is missing or ambiguous.')
    patched_binary = original_binary.replace(ORIGINAL_HEADER.encode(), PATCHED_HEADER.encode())
    return new_raw, offset, patched, patched_binary, digest(original_binary)



SUPPORTED = json.loads((Path(__file__).resolve().parent / 'supported.json').read_text())


def global_paths(install, backup):
    global INSTALL, ROOT, EXE, ASAR
    INSTALL, ROOT = install.resolve(), backup.resolve()
    EXE, ASAR = INSTALL / 'Mobalytics.exe', INSTALL / 'resources/app.asar'


def ensure_backups(action):
    """Never adopt unknown installed files or overwrite an existing backup."""
    pairs = [(ASAR, ROOT / 'app.asar.original', 'original_asar_sha256'),
             (EXE, ROOT / 'Mobalytics.exe.original', 'original_exe_sha256')]
    if all(dst.exists() for _, dst, _ in pairs):
        return
    if any(dst.exists() for _, dst, _ in pairs):
        raise RuntimeError('Incomplete backup folder. Preserve it and investigate.')
    if action != 'do':
        raise RuntimeError('No backups found. Do creates them from the supported original install.')
    for src, _, key in pairs:
        if file_hash(src) != SUPPORTED[key]:
            raise RuntimeError('Unknown or already modified install. Nothing changed.')
    ROOT.mkdir(parents=True, exist_ok=True)
    for src, dst, key in pairs:
        with src.open('rb') as source, dst.open('xb') as destination:
            shutil.copyfileobj(source, destination)
        if file_hash(dst) != SUPPORTED[key]:
            raise RuntimeError('Backup verification failed. Nothing patched.')


def powershell(command):
    return subprocess.run(['powershell.exe', '-NoProfile', '-Command', command],
                          capture_output=True, text=True, check=True)


def stop_app():
    powershell("Get-Process Mobalytics -ErrorAction SilentlyContinue | Stop-Process -Force; exit 0")
    for _ in range(30):
        result = powershell("if(Get-Process Mobalytics -ErrorAction SilentlyContinue){'running'}")
        if not result.stdout.strip():
            time.sleep(1)
            return
        time.sleep(0.5)
    raise RuntimeError('Mobalytics did not stop. Close it and retry.')


def launch():
    with (ROOT / 'latest-launch.log').open('wb') as log:
        subprocess.Popen([str(EXE)], cwd=INSTALL, stdout=log, stderr=log)
    time.sleep(6)
    result = powershell("if(Get-Process Mobalytics -ErrorAction SilentlyContinue){'running'}")
    if not result.stdout.strip():
        raise RuntimeError('Mobalytics failed to start; see latest-launch.log.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['do', 'undo', 'check'])
    parser.add_argument('--accept-signature-change', action='store_true')
    parser.add_argument('--install-dir', type=Path, default=INSTALL)
    parser.add_argument('--backup-dir', type=Path, default=ROOT)
    args = parser.parse_args()
    global_paths(args.install_dir, args.backup_dir)
    if args.action == 'do' and not args.accept_signature_change:
        raise RuntimeError('Read README.md, then pass --accept-signature-change to apply Do.')
    ensure_backups(args.action)
    new_raw, offset, patched, binary, original_exe_hash = plan()
    current_raw, _, _, _ = archive_info(ASAR)
    state = digest(current_raw)
    current_exe_hash = file_hash(EXE)
    expected = {ORIGINAL_HEADER: original_exe_hash, PATCHED_HEADER: digest(binary)}
    if state not in expected or current_exe_hash != expected[state]:
        raise RuntimeError('Installed version/files changed. Nothing modified. An app update needs a new patch review; do not restore older backups over it.')
    print('Current state:', 'PATCHED' if state == PATCHED_HEADER else 'ORIGINAL')
    if args.action == 'check':
        print('Archive integrity, executable and original backups validated.')
        return
    target = PATCHED_HEADER if args.action == 'do' else ORIGINAL_HEADER
    if state == target:
        print('Already in the requested state. Nothing changed.')
        return
    print('Applying patch. Publisher signature becomes invalid.' if args.action == 'do' else 'Restoring both original files.')
    # Keep a temporary transaction copy so failure restores the starting state.
    temp_asar = ROOT / 'transaction-app.asar'
    temp_exe = ROOT / 'transaction-Mobalytics.exe'
    shutil.copy2(ASAR, temp_asar)
    shutil.copy2(EXE, temp_exe)
    stop_app()
    completed = False
    try:
        if args.action == 'do':
            with ASAR.open('r+b') as f:
                f.seek(16)
                f.write(new_raw)
                f.seek(offset)
                f.write(patched)
            EXE.write_bytes(binary)
        else:
            shutil.copy2(ROOT / 'app.asar.original', ASAR)
            shutil.copy2(ROOT / 'Mobalytics.exe.original', EXE)
        verified_raw, _, _, _ = archive_info(ASAR)
        if digest(verified_raw) != target or file_hash(EXE) != expected[target]:
            raise RuntimeError('Post-write verification failed.')
        launch()
        completed = True
        print('Done. Mobalytics is running. In-game behavior must be checked in a match.')
    except Exception:
        stop_app()
        shutil.copy2(temp_asar, ASAR)
        shutil.copy2(temp_exe, EXE)
        print('Failure: restored the state from before this run.')
        launch()
        completed = True
        raise
    finally:
        if completed:
            temp_asar.unlink(missing_ok=True)
            temp_exe.unlink(missing_ok=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('ERROR:', error)
        raise SystemExit(1)
