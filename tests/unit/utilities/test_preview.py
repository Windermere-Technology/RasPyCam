import unittest
from unittest.mock import MagicMock, patch
from utilities.preview import generate_preview  # type: ignore
import numpy as np


class TestGeneratePreview(unittest.TestCase):
    @patch("utilities.preview.os.rename")
    @patch("utilities.preview.CameraCoreModel")
    def test_generate_preview_no_previews_enabled(
        self, mock_camera_core_model, mock_os_rename
    ):
        # Setup
        cams = {0: MagicMock(), 1: MagicMock()}
        mock_camera_core_model.show_previews = [False, False]
        mock_camera_core_model.preview_dict_lock = MagicMock()

        # Execute
        generate_preview(cams)

        # Assert
        cams[0].picam2.capture_array.assert_not_called()
        cams[1].picam2.capture_array.assert_not_called()
        mock_os_rename.assert_not_called()

    @patch("utilities.preview.os.rename")
    @patch("utilities.preview.CameraCoreModel")
    def test_generate_preview_single_preview_enabled(
        self, mock_camera_core_model, mock_os_rename
    ):
        # Setup
        cams = {0: MagicMock(), 1: MagicMock()}
        mock_camera_core_model.show_previews = [True, False]
        mock_camera_core_model.preview_dict_lock = MagicMock()
        cams[0].picam2.camera_configuration.return_value = {
            "preview_stream": {"size": (640, 480)}
        }
        cams[0].picam2.stream_configuration.return_value = {"format": "YUV420"}
        cams[0].picam2.capture_array.return_value = np.zeros(
            (480, 640), dtype=np.uint8  # Ensure single channel for YUV
        )
        cams[0].picam2.capture_metadata.return_value = {}
        cams[0].config = {
            "preview_path": "/tmp/preview.jpg",
            "preview_size": (640, 480),
            "preview_quality": 10,
        }
        cams[0].preview_stream = "preview_stream"
        mock_camera_core_model.main_camera = 0

        # Execute
        generate_preview(cams)

        # Assert
        cams[0].picam2.capture_array.assert_called_once()
        mock_os_rename.assert_called_once_with(
            "/tmp/preview.jpg.part.jpg", "/tmp/preview.jpg"
        )

    @patch("utilities.preview.os.rename")
    @patch("utilities.preview.CameraCoreModel")
    def test_generate_preview_multiple_previews_enabled(
        self, mock_camera_core_model, mock_os_rename
    ):
        # Setup
        cams = {0: MagicMock(), 1: MagicMock()}
        mock_camera_core_model.show_previews = [True, True]
        mock_camera_core_model.preview_dict_lock = MagicMock()
        cams[0].picam2.camera_configuration.return_value = {
            "preview_stream": {"size": (640, 480)}
        }
        cams[1].picam2.camera_configuration.return_value = {
            "preview_stream": {"size": (640, 480)}
        }
        cams[0].picam2.stream_configuration.return_value = {"format": "YUV420"}
        cams[1].picam2.stream_configuration.return_value = {"format": "YUV420"}
        cams[0].picam2.capture_array.return_value = np.zeros(
            (480, 640), dtype=np.uint8  # Ensure single channel for YUV
        )
        cams[1].picam2.capture_array.return_value = np.zeros(
            (480, 640), dtype=np.uint8  # Ensure single channel for YUV
        )
        cams[0].picam2.capture_metadata.return_value = {}
        cams[0].config = {
            "preview_path": "/tmp/preview.jpg",
            "preview_size": (640, 480),
            "preview_quality": 10,
        }
        cams[0].preview_stream = "preview_stream"
        cams[1].preview_stream = "preview_stream"
        mock_camera_core_model.main_camera = 0

        # Execute
        generate_preview(cams)

        # Assert
        cams[0].picam2.capture_array.assert_called_once()
        cams[1].picam2.capture_array.assert_called_once()
        mock_os_rename.assert_called_once_with(
            "/tmp/preview.jpg.part.jpg", "/tmp/preview.jpg"
        )


if __name__ == "__main__":
    unittest.main()
