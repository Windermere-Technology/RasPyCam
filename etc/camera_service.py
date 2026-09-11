#!/usr/bin/env python3
"""Stop or recover the feeder camera without killing unrelated Python processes."""
import argparse
import fcntl
import os
from pathlib import Path
import signal
import subprocess
import syslog
import time

MAIN = b'/opt/vc/bin/raspycam/main.py'


def camera_processes():
    result = {}
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            if MAIN not in (entry / 'cmdline').read_bytes().split(b'\0'):
                continue
            # Start time prevents signalling a reused PID.
            stat = (entry / 'stat').read_text().rsplit(')', 1)[1].split()
            result[int(entry.name)] = int(stat[19])
        except (OSError, ValueError):
            continue
    return result


def stop_camera():
    processes = camera_processes()
    for pid in processes:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        remaining = {pid for pid, started in camera_processes().items()
                     if processes.get(pid) == started}
        if not remaining:
            return
        time.sleep(0.25)
    killed = False
    for pid, started in camera_processes().items():
        if processes.get(pid) == started:
            killed = True
            syslog.syslog(syslog.LOG_ERR, f'RasPyCam PID {pid} failed to stop; sending SIGKILL')
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    if killed:
        for _ in range(20):
            if not any(processes.get(pid) == started
                       for pid, started in camera_processes().items()):
                return
            time.sleep(0.25)
        raise RuntimeError('Camera process has not exited; refusing a competing launch')


def check_camera():
    config = {}
    for path in ['/etc/raspimjpeg', '/var/www/html/uconfig']:
        try:
            for line in Path(path).read_text().splitlines():
                parts = line.split(None, 1)
                if len(parts) == 2 and not line.lstrip().startswith('#'):
                    config[parts[0]] = parts[1]
        except FileNotFoundError:
            pass
    processes = camera_processes()
    if processes:
        # Let startup finish, and respect a deliberately stopped/hidden preview.
        uptime = float(Path('/proc/uptime').read_text().split()[0])
        hz = os.sysconf('SC_CLK_TCK')
        if any(uptime - started / hz < 90 for started in processes.values()):
            return
        status = Path(config.get('status_file', '/dev/shm/mjpeg/status_mjpeg.txt'))
        if status.exists() and status.read_text().strip() == 'halted':
            return
        if config.get('show_preview', 'true') == 'false':
            return
        preview = Path(config.get('preview_path', '/dev/shm/mjpeg/cam.jpg'))
        try:
            if time.time() - preview.stat().st_mtime < 60:
                return
        except FileNotFoundError:
            pass
    details = []
    for path in ['/sys/class/thermal/thermal_zone0/temp', '/proc/meminfo']:
        try:
            details.append(path + ': ' + Path(path).read_text()[:350].replace('\n', ' '))
        except OSError:
            pass
    syslog.syslog(syslog.LOG_WARNING, 'Restarting stale/missing RasPyCam; ' + '; '.join(details))
    stop_camera()
    subprocess.run(['runuser', '-u', 'www-data', '--', '/usr/bin/raspimjpeg'], check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stop', action='store_true')
    args = parser.parse_args()
    with open('/run/lock/raspycam-watchdog.lock', 'w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        if args.stop:
            stop_camera()
        else:
            check_camera()


if __name__ == '__main__':
    main()
