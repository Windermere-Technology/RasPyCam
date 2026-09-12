import logging
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from utilities import diagnostics as d


class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.old_handlers = d._log.handlers[:]
        self.old_level = d._log.level
        self.old_incident = d._last_incident
        d._log.handlers = []
        d._last_incident = float('-inf')

    def tearDown(self):
        for handler in d._log.handlers:
            handler.close()
        d._log.handlers = self.old_handlers
        d._log.setLevel(self.old_level)
        d._last_incident = self.old_incident

    def test_frame_tracking_does_not_write_logs(self):
        with patch.object(d._log, 'info') as log:
            for _ in range(1000):
                d.progress('test')
                d.event('test event')
            log.assert_not_called()
        self.assertLessEqual(len(d._events), 128)

    def test_incident_contains_stacks_and_is_rate_limited(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(d.threading, 'Thread') as thread:
            path = Path(tmp) / 'diagnostics.log'
            d.configure(path)
            d.progress('test')
            d.event('recording requested')
            d.incident('test timeout')
            d.incident('duplicate timeout')
            text = path.read_text()
            self.assertIn('test timeout', text)
            self.assertIn('recording requested', text)
            self.assertIn('test_incident_contains_stacks', text)
            self.assertNotIn('duplicate timeout', text)
            thread.assert_called_once()

    def test_rotation_bounds_retained_files(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(d, 'LOG_BYTES', 2048):
            d.configure(Path(tmp) / 'diagnostics.log')
            for _ in range(100):
                d._log.info('x' * 500)
            files = list(Path(tmp).iterdir())
            self.assertEqual(len(files), 4)
            self.assertTrue(all(path.stat().st_size <= 2048 for path in files))

    def test_unwritable_log_does_not_prevent_startup(self):
        with patch.object(d, 'RotatingFileHandler', side_effect=PermissionError), patch.object(logging, 'exception'):
            d.configure('/unwritable/diagnostics.log')
