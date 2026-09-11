"""Real OS pipe backpressure must never block encoder callbacks."""
import subprocess
import sys
import threading
import time
import unittest
from unittest.mock import patch, MagicMock

from utilities.video_output import RecordingOutput


class StalledOutputTests(unittest.TestCase):
    def start_nonreader(self):
        process = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(1)'],
                                   stdin=subprocess.PIPE, bufsize=0)
        output = RecordingOutput('/tmp/unused.mp4')
        output.WRITE_TIMEOUT = 0.2
        self.failed = threading.Event()
        output.error_callback = lambda error: self.failed.set()
        with patch('utilities.video_output.subprocess.Popen', return_value=process):
            output.start()
        self.addCleanup(output.stop)
        return output

    def test_nonreader_times_out_without_blocking_encoder(self):
        with patch('utilities.video_output.diagnostics.incident'), patch('utilities.video_output.diagnostics.process_snapshot'):
            output = self.start_nonreader()
            start = time.monotonic()
            output.outputframe(b'x' * 1000000)
            self.assertLess(time.monotonic() - start, 0.15)
            self.assertTrue(self.failed.wait(2))
            self.assertIsInstance(output._error, TimeoutError)
            output.stop()
            self.assertFalse(output._thread.is_alive())
            self.assertIsNone(output._process)

    def test_capacity_failure_does_not_silently_drop_frames(self):
        with patch('utilities.video_output.diagnostics.incident'), patch('utilities.video_output.diagnostics.process_snapshot'):
            output = self.start_nonreader()
            output.MAX_BYTES = 1024
            output.outputframe(b'x' * 1025)
            self.assertTrue(self.failed.wait(2))
            self.assertIn('capacity', str(output._error))
            self.assertEqual(output._bytes, 0)
            output.stop()

    def test_stalled_process_termination_is_reaped_without_camera_error(self):
        output = RecordingOutput('/tmp/unused.mp4')
        output._process = MagicMock()
        process = output._process
        process.wait.side_effect = [subprocess.TimeoutExpired('ffmpeg', 5), -15]
        process.returncode = -15
        output._error = TimeoutError('stalled writer')
        output._condition = threading.Condition()
        output._thread = MagicMock()
        output._thread.is_alive.return_value = False
        output.stop()
        process.terminate.assert_called_once()
        self.assertIsNone(output._process)
