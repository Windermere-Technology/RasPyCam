import unittest
from unittest.mock import MagicMock, patch
from utilities.record import start_recording, stop_recording, toggle_cam_record  # type: ignore


class TestRecordFunctions(unittest.TestCase):
    @patch("utilities.record.FfmpegOutput")
    @patch("utilities.record.FileOutput")
    def test_start_recording_already_capturing(self, MockFileOutput, MockFfmpegOutput):
        cam = MagicMock()
        cam.capturing_video = True

        result = start_recording(cam)

        cam.print_to_logfile.assert_called_once_with("Already capturing. Ignore")
        self.assertFalse(result)

    @patch("utilities.record.FfmpegOutput")
    @patch("utilities.record.FileOutput")
    def test_start_recording_success(self, MockFileOutput, MockFfmpegOutput):
        cam = MagicMock()
        cam.capturing_video = False
        cam.config = {"video_output_path": "test_path"}
        cam.make_filename.return_value = "test_output.mp4"
        cam.record_stream = "main"

        result = start_recording(cam)

        cam.print_to_logfile.assert_called_once_with("Capturing started")
        cam.setup_video_encoder.assert_called_once()
        cam.generate_thumbnail.assert_called_once_with("v", "test_output.mp4")
        cam.make_filename.assert_called_once_with("test_path")
        cam.picam2.start_encoder.assert_called_once_with(
            cam.video_encoder, MockFfmpegOutput.return_value, name="main"
        )
        cam.set_status.assert_called_once_with("video")
        self.assertTrue(result)

    def test_stop_recording_already_stopped(self):
        cam = MagicMock()
        cam.capturing_video = False

        result = stop_recording(cam)

        cam.print_to_logfile.assert_called_once_with("Already stopped. Ignore")
        self.assertFalse(result)

    def test_stop_recording_success(self):
        cam = MagicMock()
        cam.capturing_video = True
        cam.video_encoder.running = True
        cam.current_video_path = "test_output.mp4"

        result = stop_recording(cam)

        cam.print_to_logfile.assert_called_once_with("Capturing stopped")
        cam.picam2.stop_encoder.assert_called_once()
        cam.set_status.assert_called_once_with("ready")
        self.assertTrue(result)

    @patch("utilities.record.start_recording")
    @patch("utilities.record.stop_recording")
    def test_toggle_cam_record_start(self, mock_stop_recording, mock_start_recording):
        cam = MagicMock()
        mock_start_recording.return_value = True

        result = toggle_cam_record(cam, True)

        mock_start_recording.assert_called_once_with(cam)
        mock_stop_recording.assert_not_called()
        self.assertTrue(result)

    @patch("utilities.record.start_recording")
    @patch("utilities.record.stop_recording")
    def test_toggle_cam_record_stop(self, mock_stop_recording, mock_start_recording):
        cam = MagicMock()
        mock_stop_recording.return_value = True

        result = toggle_cam_record(cam, False)

        mock_stop_recording.assert_called_once_with(cam)
        mock_start_recording.assert_not_called()
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
