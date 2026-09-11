#!/usr/bin/env python3
"""Install this checkout's reliability update with a backup and automatic rollback."""
import fcntl
import importlib.util
import json
import os
import pwd
from pathlib import Path
import shutil
import subprocess
import time

SOURCE = Path(__file__).resolve().parents[1]
TARGET = Path('/opt/vc/bin/raspycam')
WATCHDOG = Path('/home/brian/restart_raspimjpg')
STATUS = Path('/dev/shm/mjpeg/status_mjpeg.txt')
PREVIEW = Path('/dev/shm/mjpeg/cam.jpg')


def wait_preview():
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if PREVIEW.exists() and time.time() - PREVIEW.stat().st_mtime < 5:
            if STATUS.exists() and 'ready' in STATUS.read_text():
                return
        time.sleep(1)
    raise RuntimeError('No fresh camera preview within 60 seconds')


def main():
    if os.geteuid() != 0:
        raise SystemExit('Run with sudo to update the installed camera service.')
    with open('/run/lock/raspycam-watchdog.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if not STATUS.exists() or 'ready' not in STATUS.read_text():
            raise SystemExit('Camera is not idle/ready; refusing to interrupt a recording.')
        spec = importlib.util.spec_from_file_location('service', SOURCE / 'etc/camera_service.py')
        service = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(service)
        pairs = [(p, TARGET / p.relative_to(SOURCE / 'app'))
                 for p in (SOURCE / 'app').rglob('*.py')]
        pairs += [(SOURCE / 'etc/raspycam', TARGET / 'raspycam'),
                  (SOURCE / 'etc/camera_service.py', TARGET / 'camera_service.py'),
                  (SOURCE / 'etc/restart_raspimjpg', WATCHDOG)]
        backup = Path('/var/backups') / time.strftime('raspycam-%Y%m%d-%H%M%S')
        backup.mkdir(mode=0o700)
        manifest = []
        for index, (source, target) in enumerate(pairs):
            saved = backup / str(index)
            exists = target.exists()
            if exists:
                shutil.copy2(target, saved)
            manifest.append({'target': str(target), 'saved': str(saved), 'existed': exists})
        (backup / 'manifest.json').write_text(json.dumps(manifest, indent=2))
        print(f'Backup: {backup}', flush=True)
        log_dir = Path('/var/log/raspycam')
        log_dir.mkdir(mode=0o750, exist_ok=True)
        camera_user = pwd.getpwnam('www-data')
        os.chown(log_dir, camera_user.pw_uid, camera_user.pw_gid)
        service.stop_camera()
        try:
            for source, target in pairs:
                # Install atomically so a concurrent reader cannot see partial source.
                staged = target.with_name(target.name + '.new')
                shutil.copyfile(source, staged)
                staged.chmod(0o755 if target.name in ('raspycam', 'restart_raspimjpg') else 0o644)
                os.replace(staged, target)
            subprocess.run(['runuser', '-u', 'www-data', '--', '/usr/bin/raspimjpeg'], check=True)
            wait_preview()
            if len(service.camera_processes()) != 1:
                raise RuntimeError('Expected exactly one camera process')
        except Exception:
            service.stop_camera()
            for item in manifest:
                target = Path(item['target'])
                if item['existed']:
                    shutil.copy2(item['saved'], target)
                elif target.exists():
                    target.unlink()
            subprocess.run(['runuser', '-u', 'www-data', '--', '/usr/bin/raspimjpeg'], check=True)
            print('Restored previous files and requested camera restart.', flush=True)
            raise
        print('Installed successfully: one camera process and a fresh preview.', flush=True)


if __name__ == '__main__':
    main()
