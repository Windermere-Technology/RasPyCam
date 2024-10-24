import unittest
from unittest.mock import MagicMock, patch
from utilities.capture import capture_still_image, capture_stitched_image
from PIL import Image
import numpy as np


class TestCaptureStillImage(unittest.TestCase):
    @patch("utilities.capture.Image.fromarray")
    def test_capture_still_image(self, mock_fromarray):
        # Mock the camera object
        cam = MagicMock()
        cam.config = {"image_output_path": "test_path"}
        cam.picam2.capture_array.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
        cam.picam2.capture_metadata.return_value = {}
        mock_image = MagicMock(spec=Image.Image)
        mock_fromarray.return_value = mock_image

        # Call the function
        capture_still_image(cam)

        # Assertions
        cam.capture_metadata.assert_called_once()
        cam.make_filename.assert_called_once_with("test_path")
        cam.picam2.capture_array.assert_called_once_with("main")
        mock_fromarray.assert_called_once()
        cam.picam2.helpers.save.assert_called_once()
        cam.generate_thumbnail.assert_called_once_with(
            "i", cam.make_filename.return_value
        )

    @patch("utilities.capture.Image.fromarray")
    def test_capture_still_image_no_metadata(self, mock_fromarray):
        # Mock the camera object without capture_metadata method
        cam = MagicMock()
        del cam.capture_metadata
        cam.config = {"image_output_path": "test_path"}
        cam.picam2.capture_array.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_image = MagicMock(spec=Image.Image)
        mock_fromarray.return_value = mock_image

        # Call the function
        capture_still_image(cam)

        # Assertions
        cam.make_filename.assert_called_once_with("test_path")
        cam.picam2.capture_array.assert_called_once_with("main")
        mock_fromarray.assert_called_once()
        cam.picam2.helpers.save.assert_called_once_with(
            mock_image, {}, cam.make_filename.return_value
        )
        cam.generate_thumbnail.assert_called_once_with(
            "i", cam.make_filename.return_value
        )


class TestCaptureStitchedImage(unittest.TestCase):
    @patch("utilities.capture.Image.frombuffer")
    def test_capture_stitched_image(self, mock_frombuffer):
        # Mock the camera objects
        cam1 = MagicMock()
        cam2 = MagicMock()
        cam1.config = {"image_output_path": "test_path"}
        cam2.config = {"image_output_path": "test_path"}
        cam1.picam2.capture_array.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
        cam2.picam2.capture_array.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
        cam1.picam2.capture_metadata.return_value = {}
        cam2.picam2.capture_metadata.return_value = {}
        cams = {0: cam1, 1: cam2}
        mock_image = MagicMock(spec=Image.Image)
        mock_frombuffer.return_value = mock_image

        # Call the function
        capture_stitched_image(0, cams, axis=0)

        # Assertions
        cam1.picam2.capture_metadata.assert_called_once()
        cam1.make_filename.assert_called_once_with("test_path")
        cam1.picam2.capture_array.assert_called_once_with(cam1.still_stream)
        cam2.picam2.capture_array.assert_called_once_with(cam2.still_stream)
        mock_frombuffer.assert_called_once()
        cam1.picam2.helpers.save.assert_called_once_with(
            mock_image, {}, cam1.make_filename.return_value
        )
        cam1.generate_thumbnail.assert_called_once_with(
            "i", cam1.make_filename.return_value
        )

    @patch("utilities.capture.Image.frombuffer")
    def test_capture_stitched_image_different_sizes(self, mock_frombuffer):
        # Mock the camera objects with different image sizes
        cam1 = MagicMock()
        cam2 = MagicMock()
        cam1.config = {"image_output_path": "test_path"}
        cam2.config = {"image_output_path": "test_path"}
        cam1.picam2.capture_array.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
        cam2.picam2.capture_array.return_value = np.zeros((100, 150, 3), dtype=np.uint8)
        cam1.picam2.capture_metadata.return_value = {}
        cam2.picam2.capture_metadata.return_value = {}
        cams = {0: cam1, 1: cam2}
        mock_image = MagicMock(spec=Image.Image)
        mock_frombuffer.return_value = mock_image

        # Call the function
        capture_stitched_image(0, cams, axis=1)

        # Assertions
        cam1.picam2.capture_metadata.assert_called_once()
        cam1.make_filename.assert_called_once_with("test_path")
        cam1.picam2.capture_array.assert_called_once_with(cam1.still_stream)
        cam2.picam2.capture_array.assert_called_once_with(cam2.still_stream)
        mock_frombuffer.assert_called_once()
        cam1.picam2.helpers.save.assert_called_once_with(
            mock_image, {}, cam1.make_filename.return_value
        )
        cam1.generate_thumbnail.assert_called_once_with(
            "i", cam1.make_filename.return_value
        )

    @patch("utilities.capture.Image.frombuffer")
    def test_capture_stitched_image_horizontal_padding(self, mock_frombuffer):
        # Mock the camera objects with different widths
        cam1 = MagicMock()
        cam2 = MagicMock()
        cam1.config = {"image_output_path": "test_path"}
        cam2.config = {"image_output_path": "test_path"}
        cam1.picam2.capture_array.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
        cam2.picam2.capture_array.return_value = np.zeros((100, 150, 3), dtype=np.uint8)
        cam1.picam2.capture_metadata.return_value = {}
        cam2.picam2.capture_metadata.return_value = {}
        cams = {0: cam1, 1: cam2}
        mock_image = MagicMock(spec=Image.Image)
        mock_frombuffer.return_value = mock_image

        # Call the function
        capture_stitched_image(0, cams, axis=0)

        # Assertions
        cam1.picam2.capture_metadata.assert_called_once()
        cam1.make_filename.assert_called_once_with("test_path")
        cam1.picam2.capture_array.assert_called_once_with(cam1.still_stream)
        cam2.picam2.capture_array.assert_called_once_with(cam2.still_stream)
        mock_frombuffer.assert_called_once()
        cam1.picam2.helpers.save.assert_called_once_with(
            mock_image, {}, cam1.make_filename.return_value
        )
        cam1.generate_thumbnail.assert_called_once_with(
            "i", cam1.make_filename.return_value
        )

    @patch("utilities.capture.Image.frombuffer")
    def test_capture_stitched_image_vertical_padding(self, mock_frombuffer):
        # Mock the camera objects with different heights
        cam1 = MagicMock()
        cam2 = MagicMock()
        cam1.config = {"image_output_path": "test_path"}
        cam2.config = {"image_output_path": "test_path"}
        cam1.picam2.capture_array.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
        cam2.picam2.capture_array.return_value = np.zeros((150, 100, 3), dtype=np.uint8)
        cam1.picam2.capture_metadata.return_value = {}
        cam2.picam2.capture_metadata.return_value = {}
        cams = {0: cam1, 1: cam2}
        mock_image = MagicMock(spec=Image.Image)
        mock_frombuffer.return_value = mock_image

        # Call the function
        capture_stitched_image(0, cams, axis=1)

        # Assertions
        cam1.picam2.capture_metadata.assert_called_once()
        cam1.make_filename.assert_called_once_with("test_path")
        cam1.picam2.capture_array.assert_called_once_with(cam1.still_stream)
        cam2.picam2.capture_array.assert_called_once_with(cam2.still_stream)
        mock_frombuffer.assert_called_once()
        cam1.picam2.helpers.save.assert_called_once_with(
            mock_image, {}, cam1.make_filename.return_value
        )
        cam1.generate_thumbnail.assert_called_once_with(
            "i", cam1.make_filename.return_value
        )


if __name__ == "__main__":
    unittest.main()
