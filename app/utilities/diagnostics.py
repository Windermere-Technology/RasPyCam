"""Bounded incident diagnostics; frame tracking stays entirely in memory."""
from collections import deque
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import traceback

LOG_BYTES = 1024 * 1024
LOG_BACKUPS = 3
_events = deque(maxlen=128)
_progress = {}
_incident_lock = threading.Lock()
_last_incident = float('-inf')
_log = logging.getLogger('raspycam.diagnostics')
_log.addHandler(logging.NullHandler())
_log.propagate = False


def configure(path='/var/log/raspycam/diagnostics.log'):
    try:
        handler = RotatingFileHandler(path, maxBytes=LOG_BYTES, backupCount=LOG_BACKUPS)
        handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
        _log.addHandler(handler)
        _log.setLevel(logging.INFO)
        _log.info('diagnostics enabled pid=%s', os.getpid())
        event('diagnostics enabled')
    except OSError:
        logging.exception('Could not open bounded diagnostics log')


def event(message):
    _events.append((time.time(), str(message)[:1000]))


def progress(stream):
    count, _ = _progress.get(stream, (0, 0))
    _progress[stream] = (count + 1, time.monotonic())


def _system_snapshot():
    try:
        for path in ('/proc/meminfo', '/proc/self/status', '/sys/class/thermal/thermal_zone0/temp'):
            try:
                with open(path) as source:
                    _log.info('%s: %s', path, source.read(4096))
            except OSError as error:
                _log.info('%s unavailable: %s', path, error)
        for path in ('/opt/vc/bin/raspycam', '/var/www/html/media'):
            try:
                _log.info('disk %s: %s', path, shutil.disk_usage(path))
            except OSError as error:
                _log.info('disk %s unavailable: %s', path, error)
        for command in (['vcgencmd', 'get_throttled'],
                        ['journalctl', '-k', '-n', '60', '--no-pager', '-o', 'short-iso']):
            try:
                result = subprocess.run(command, capture_output=True, text=True, timeout=2)
                _log.info('%s exit=%s: %s', command, result.returncode,
                          (result.stdout + result.stderr)[-16000:])
            except (OSError, subprocess.TimeoutExpired) as error:
                _log.info('%s unavailable: %s', command, error)
    except Exception:
        # Diagnostics must never interfere with recovery.
        logging.exception('Incident system snapshot failed')


def incident(reason):
    """Capture Python stacks before cleanup; slow system probes run separately."""
    global _last_incident
    if not _incident_lock.acquire(blocking=False):
        return
    try:
        now = time.monotonic()
        if now - _last_incident < 60:
            return
        _last_incident = now
        _log.info('INCIDENT pid=%s %s', os.getpid(), str(reason)[:1000])
        _log.info('progress (count, seconds since last): %s',
                  {key: (count, round(now - last, 3))
                   for key, (count, last) in _progress.copy().items()})
        _log.info('recent events (Unix time): %s', list(_events))
        names = {t.ident: t.name for t in threading.enumerate()}
        for ident, frame in sys._current_frames().items():
            _log.info('thread %s (%s):\n%s', names.get(ident, '?'), ident,
                      ''.join(traceback.format_stack(frame, limit=30))[-16000:])
        threading.Thread(target=_system_snapshot, name='incident-snapshot', daemon=True).start()
    except Exception:
        logging.exception('Incident capture failed')
    finally:
        _incident_lock.release()


def process_snapshot(pid):
    """Read bounded FFmpeg process state before closing its input pipe."""
    for name in ('status', 'wchan', 'syscall', 'io'):
        try:
            with open(f'/proc/{pid}/{name}') as source:
                _log.info('FFmpeg pid=%s %s: %s', pid, name, source.read(4096))
        except OSError as error:
            _log.info('FFmpeg pid=%s %s unavailable: %s', pid, name, error)
