"""Hardware-free regression tests; run with PYTHONPATH=app python3 -m unittest discover -s tests/reliability."""
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from utilities.command_pipe import CommandReader
from utilities.record import start_recording, stop_recording
from utilities.video_output import RecordingOutput
from core.model import CameraCoreModel
from core.process import read_pipe, run_worker, shutdown


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.r, self.w = os.pipe()
        os.set_blocking(self.r, False)
        self.reader = CommandReader()

    def tearDown(self):
        os.close(self.r)
        if self.w is not None:
            os.close(self.w)

    def test_combined_start_stop_preserved(self):
        os.write(self.w, b'ca 1\nca 0\n')
        self.assertEqual(read_pipe(self.r, self.reader), ('ca', '1'))
        self.assertEqual(read_pipe(self.r, self.reader), ('ca', '0'))

    def test_partial_command_waits_for_completion(self):
        os.write(self.w, b'ca ')
        self.assertIsNone(self.reader.read(self.r))
        self.assertIsNone(self.reader.read(self.r))
        os.write(self.w, b'1\nca 0\n')
        self.assertEqual(self.reader.read(self.r), 'ca 1')
        self.assertEqual(self.reader.read(self.r), 'ca 0')

    def test_legacy_writer_close_without_newline(self):
        os.write(self.w, b'ca 0')
        os.close(self.w)
        self.w = None
        self.assertIsNone(self.reader.read(self.r))
        self.assertEqual(self.reader.read(self.r), 'ca 0')

    def test_bad_or_oversize_commands_do_not_lose_stop(self):
        os.write(self.w, b'x' * 300 + b'\n\xff\nca 0\n')
        self.assertEqual(self.reader.read(self.r), 'ca 0')

    def test_actual_fifo_writer_close(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'FIFO'
            os.mkfifo(path)
            fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
            try:
                with open(path, 'wb') as writer:
                    writer.write(b'ca 1\nca 0\n')
                self.assertEqual(read_pipe(fd, self.reader), ('ca', '1'))
                self.assertEqual(read_pipe(fd, self.reader), ('ca', '0'))
            finally:
                os.close(fd)


class LifecycleTests(unittest.TestCase):
    def test_worker_failure_requests_shutdown(self):
        CameraCoreModel.process_running = True
        def failed():
            raise TimeoutError('no camera frames')
        with self.assertLogs(level='ERROR'):
            run_worker(failed)
        self.assertFalse(CameraCoreModel.process_running)

    def test_shutdown_finalizes_before_join_and_teardown(self):
        CameraCoreModel.fifo_fd = None
        cam = MagicMock(capturing_video=True)
        events = []
        worker = MagicMock()
        worker.join.side_effect = lambda **kw: events.append('join')
        cam.teardown.side_effect = lambda: events.append('teardown')
        with patch('core.process.toggle_cam_record', side_effect=lambda *a: events.append('stop')):
            shutdown({0: cam}, [worker])
        self.assertEqual(events, ['stop', 'join', 'teardown'])
        worker.join.assert_called_once_with(timeout=7)

    def test_stop_failure_clears_recording_flags(self):
        cam = MagicMock(capturing_video=True)
        cam.picam2.stop_encoder.side_effect = RuntimeError('failed')
        with self.assertRaises(RuntimeError):
            stop_recording(cam)
        self.assertFalse(cam.capturing_video)
        self.assertIsNone(cam.record_until)
        cam.set_status.assert_not_called()

    @patch('utilities.record.FfmpegOutput')
    def test_encoder_start_failure_remains_eligible_for_cleanup(self, output):
        cam = MagicMock(capturing_video=False)
        cam.make_filename.return_value = '/tmp/test.mp4'
        cam.picam2.start_encoder.side_effect = RuntimeError('partial start')
        with self.assertRaises(RuntimeError):
            start_recording(cam)
        self.assertTrue(cam.capturing_video)
        with patch('utilities.record.diagnostics.incident'):
            output.return_value.error_callback(BrokenPipeError('ffmpeg exited'))
        self.assertEqual(cam.recording_error, 'ffmpeg exited')

    @patch('utilities.video_output.os.set_blocking')
    @patch('utilities.video_output.subprocess.Popen')
    def test_fragmented_mp4_and_space_in_filename(self, popen, set_blocking):
        output = RecordingOutput('/tmp/cat feed.mp4')
        output.start()
        command = popen.call_args.args[0]
        self.assertEqual(command[-1], '/tmp/cat feed.mp4')
        self.assertIn('+frag_keyframe+empty_moov+default_base_moof', command)
        self.assertNotIn('preexec_fn', popen.call_args.kwargs)
        popen.return_value.wait.return_value = 0
        output.stop()

    @patch('utilities.video_output.os.set_blocking')
    @patch('utilities.video_output.subprocess.Popen')
    def test_failed_ffmpeg_is_reaped_even_after_callback_clears_reference(self, popen, set_blocking):
        output = RecordingOutput('/tmp/cat.mp4')
        output.start()
        output.ffmpeg = None
        popen.return_value.wait.return_value = 1
        with self.assertRaisesRegex(RuntimeError, 'status 1'):
            output.stop()
        popen.return_value.stdin.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
