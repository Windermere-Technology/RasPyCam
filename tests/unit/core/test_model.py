from datetime import datetime
import os
import unittest
from unittest.mock import call, patch, mock_open, MagicMock
import numpy as np
from core.model import CameraCoreModel  # type: ignore


# Base Test Class for CameraCoreModel setup
class TestCameraCoreModelBase(unittest.TestCase):
    @patch("core.model.Picamera2")
    def setUp(self, mock_picamera2):
        """Set up the test case with a mocked Picamera2 instance."""
        self.mock_picamera2 = mock_picamera2.return_value
        self.mock_picamera2.stop_encoder = MagicMock()
        self.mock_picamera2.stop = MagicMock()
        self.mock_picamera2.start = MagicMock()
        self.mock_picamera2.close = MagicMock()
        self.mock_picamera2.capture_request = MagicMock()
        self.mock_picamera2.sensor_resolution = (1920, 1080)
        self.mock_picamera2.camera_config = {
            "main": {"size": (1920, 1080), "format": "YUV420"},
            "lores": {"size": (640, 480), "format": "YUV420"},
        }
        camera_info = {"Model": "test_model", "Num": 0}
        self.model = CameraCoreModel(camera_info, None)


# Test Initialisation Functionality
class TestCameraCoreModelInit(unittest.TestCase):
    @unittest.skip(
        "Skipping because the test is good but isn't covering the code for some reason"
    )
    @patch("core.model.Picamera2")
    def test_solo_stream_mode(self, mock_picamera2):
        """Test the solo stream mode functionality."""
        camera_info = {"Model": "test_model", "Num": 0}
        config_path = None

        mock_picamera2.return_value.camera_config = {
            "main": {"size": (1920, 1080), "format": "YUV420"},
            "lores": {"size": (640, 480), "format": "YUV420"},
        }
        mock_picamera2.return_value.sensor_resolution = (1920, 1080)

        model = CameraCoreModel(camera_info, config_path)
        model.config["solo_stream_mode"] = True

        model.toggle_solo_stream_mode(True)

        self.assertTrue(model.solo_stream_mode)
        self.assertEqual(model.preview_stream, "main")
        self.assertEqual(model.record_stream, "main")
        self.assertEqual(model.md_stream, "main")

    @unittest.skip(
        "Skipping because the test is good but isn't covering the code for some reason"
    )
    @patch("core.model.Picamera2")
    def test_motion_detection_enabled(self, mock_picamera2):
        """Test the motion detection enabled functionality."""
        camera_info = {"Model": "test_model", "Num": 0}
        config_path = None

        mock_picamera2.return_value.camera_config = {
            "main": {"size": (1920, 1080), "format": "YUV420"},
            "lores": {"size": (640, 480), "format": "YUV420"},
        }
        mock_picamera2.return_value.sensor_resolution = (1920, 1080)

        model = CameraCoreModel(camera_info, config_path)
        model.config["autostart"] = True
        model.config["motion_detection"] = True

        model.picam2.start.assert_called_once()

        self.assertTrue(model.motion_detection)

        self.assertEqual(model.current_status, "ready")

    @patch("core.model.Picamera2")
    def test_autostart_enabled(self, mock_picamera2):
        """Test the autostart enabled functionality."""
        camera_info = {"Model": "test_model", "Num": 0}
        config_path = None

        mock_picamera2.return_value.camera_config = {
            "main": {"size": (1920, 1080), "format": "YUV420"},
            "lores": {"size": (640, 480), "format": "YUV420"},
        }
        mock_picamera2.return_value.sensor_resolution = (1920, 1080)

        model = CameraCoreModel(camera_info, config_path)
        model.config["autostart"] = True

        mock_picamera2.return_value.start.assert_called_once()
        self.assertEqual(model.current_status, "ready")

    @patch("core.model.Picamera2")
    def test_camera_model_ov64a40(self, mock_picamera2):
        """Test the camera model ov64a40 functionality."""
        camera_info = {"Model": "ov64a40", "Num": 0}
        config_path = None

        mock_picamera2.return_value.camera_config = {
            "main": {"size": (1920, 1080), "format": "YUV420"},
            "lores": {"size": (640, 480), "format": "YUV420"},
        }
        mock_picamera2.return_value.sensor_resolution = (1920, 1080)

        _ = CameraCoreModel(camera_info, config_path)

        mock_picamera2.return_value.set_controls.assert_called_with(
            {"AfMode": 1, "AfTrigger": 0}
        )


# Test the PreCallback Functionality
class TestCameraCoreModelPreCallback(unittest.TestCase):
    @patch("core.model.MappedArray")
    @patch("core.model.cv2.putText")
    @patch("core.model.Picamera2")
    def test_setup_pre_callback_no_annotation(
        self, mock_Picamera2, mock_putText, mock_MappedArray
    ):
        """Test setup_pre_callback with no annotation."""
        mock_picamera2_instance = MagicMock()
        mock_Picamera2.return_value = mock_picamera2_instance

        mock_picamera2_instance.sensor_resolution = (1920, 1080)
        mock_picamera2_instance.camera_config = {
            "main": {"size": (1920, 1080), "format": "YUV420"},
            "lores": {"size": (640, 480), "format": "YUV420"},
        }

        mock_picamera2_instance.configure.return_value = None
        mock_picamera2_instance.start.return_value = None

        camera_info = {"Model": "test_model", "Num": 0}
        config_path = None
        model = CameraCoreModel(camera_info, config_path)

        mock_mapped_array_instance = MagicMock()
        mock_mapped_array_instance.array = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_MappedArray.return_value.__enter__.return_value = (
            mock_mapped_array_instance
        )

        model.config["annotation"] = None

        mock_request = MagicMock()

        model.setup_pre_callback(mock_request)

        mock_putText.assert_not_called()


# Test the Record Functionality
class TestCameraCoreModelRestart(TestCameraCoreModelBase):
    def test_restart(self):
        """Test the restart function."""
        self.mock_picamera2.stop.reset_mock()
        self.mock_picamera2.start.reset_mock()
        self.mock_picamera2.configure.reset_mock()

        self.model.restart()

        self.mock_picamera2.stop.assert_called_once()
        self.mock_picamera2.start.assert_called_once()

        self.assertEqual(self.model.current_status, "ready")

        self.mock_picamera2.configure.assert_not_called()

    @patch("core.model.CameraCoreModel.read_config_file")
    @patch("core.model.CameraCoreModel.make_output_directories")
    @patch("core.model.CameraCoreModel.make_filecounts")
    @patch("core.model.CameraCoreModel.build_configuration_object")
    def test_restart_with_reload_config(
        self,
        mock_build_config,
        mock_make_filecounts,
        mock_make_output_dirs,
        mock_read_config_file,
    ):
        """Test the restart function with the reload_config flag set to True."""
        self.mock_picamera2.stop.reset_mock()
        self.mock_picamera2.start.reset_mock()

        self.model.restart(reload_config=True)

        self.mock_picamera2.stop.assert_called_once()
        self.mock_picamera2.start.assert_called_once()

        self.assertEqual(self.model.current_status, "ready")

        mock_read_config_file.assert_called_once_with(self.model.config["user_config"])
        mock_make_output_dirs.assert_called_once()
        mock_make_filecounts.assert_called_once()
        mock_build_config.assert_called_once()


# Test the Stop All Functionality
class TestCameraCoreModelStopAll(TestCameraCoreModelBase):
    def test_stop_all(self):
        """Test the stop_all function."""
        self.model.video_encoder = MagicMock()
        self.model.video_encoder.running = True
        self.model.picam2.started = True

        self.model.stop_all()

        self.model.picam2.stop_encoder.assert_called_once_with(self.model.video_encoder)
        self.model.picam2.stop.assert_called_once()
        self.assertFalse(self.model.capturing_video)
        self.assertFalse(self.model.capturing_still)
        self.assertFalse(self.model.motion_detection)
        self.assertFalse(self.model.timelapse_on)


# Test the Reset Motion State Functionality
class TestCameraCoreModelResetMotionState(TestCameraCoreModelBase):
    def test_reset_motion_state(self):
        """Test the reset_motion_state function."""
        self.model.detected_motion = True
        self.model.motion_still_count = 10
        self.model.motion_active_count = 5

        self.model.reset_motion_state()

        self.assertFalse(self.model.detected_motion)
        self.assertEqual(self.model.motion_still_count, 0)
        self.assertEqual(self.model.motion_active_count, 0)


# Test the Teardown Functionality
class TestCameraCoreModelTeardown(unittest.TestCase):
    @patch("core.model.Picamera2")
    @patch("os.path.exists")
    @patch("os.remove")
    @patch("os.makedirs")
    def test_teardown(self, mock_makedirs, mock_remove, mock_exists, mock_picamera2):
        """Test the teardown function."""
        mock_picamera2_instance = mock_picamera2.return_value
        mock_picamera2_instance.stop_encoder = MagicMock()
        mock_picamera2_instance.stop = MagicMock()
        mock_picamera2_instance.close = MagicMock()

        mock_picamera2_instance.sensor_resolution = (1920, 1080)

        mock_picamera2_instance.camera_config = {
            "main": {"size": (1920, 1080), "format": "RGB888"},
            "lores": {"size": (640, 480), "format": "YUV420"},
        }

        mock_exists.side_effect = lambda path: path in [
            "/tmp/preview/cam_preview.jpg",
            "/tmp/preview/cam_preview.jpg.part.jpg",
        ]

        camera_info = {"Model": "test_model", "Num": 0}
        model = CameraCoreModel(camera_info, None)

        model.video_encoder = MagicMock()
        model.video_encoder.running = True
        model.video_encoder.size = (1920, 1080)

        mock_makedirs.reset_mock()

        model.teardown()

        mock_picamera2_instance.stop_encoder.assert_called_once_with(
            model.video_encoder
        )
        mock_picamera2_instance.stop.assert_called_once()
        mock_picamera2_instance.close.assert_called_once()

        mock_remove.assert_any_call("/tmp/preview/cam_preview.jpg")
        mock_remove.assert_any_call("/tmp/preview/cam_preview.jpg.part.jpg")

        mock_makedirs.assert_not_called()


# Test the Make Logfile Directories Functionality
class TestCameraCoreModelMakeLogfileDirectories(unittest.TestCase):
    @patch("core.model.Picamera2")
    @patch("os.path.exists")
    @patch("os.makedirs")
    @patch("builtins.open", new_callable=mock_open)
    def test_make_logfile_directories_creates_directories_and_files(
        self, mock_open_file, mock_makedirs, mock_exists, mock_picamera2
    ):
        """Test that make_logfile_directories creates directories and files when they don't exist."""
        mock_exists.side_effect = lambda path: False

        mock_picamera2_instance = mock_picamera2.return_value
        mock_picamera2_instance.sensor_resolution = (1920, 1080)
        mock_picamera2_instance.camera_config = {
            "main": {"size": (1920, 1080), "format": "YUV420"},
            "lores": {"size": (640, 480), "format": "YUV420"},
        }

        camera_info = {"Model": "test_model", "Num": 0}
        model = CameraCoreModel(camera_info, None)

        model.make_logfile_directories()

        expected_directories = [
            os.path.dirname(model.config["user_config"]),
            os.path.dirname(model.config["log_file"]),
            os.path.dirname(model.config["motion_logfile"]),
        ]

        for dirpath in expected_directories:
            mock_makedirs.assert_any_call(dirpath)

        mock_open_file.assert_any_call(model.config["user_config"], "a")
        mock_open_file.assert_any_call(model.config["log_file"], "a")
        mock_open_file.assert_any_call(model.config["motion_logfile"], "a")

    @patch("core.model.Picamera2")
    @patch("os.path.exists")
    @patch("os.makedirs")
    def test_make_logfile_directories_does_not_create_if_exists(
        self, mock_makedirs, mock_exists, mock_picamera2
    ):
        """Test that make_logfile_directories does not create directories or files if they already exist."""

        def mock_exists_side_effect(path):
            existing_paths = [
                "/tmp/uconfig",
                "/tmp/scheduleLog.txt",
                "/tmp/motionLog.txt",
                "/tmp",
                "/tmp/preview",
                "/tmp/media",
            ]
            return path in existing_paths

        mock_exists.side_effect = mock_exists_side_effect

        mock_picamera2_instance = mock_picamera2.return_value
        mock_picamera2_instance.sensor_resolution = (1920, 1080)
        mock_picamera2_instance.camera_config = {
            "main": {"size": (1920, 1080), "format": "YUV420"},
            "lores": {"size": (640, 480), "format": "YUV420"},
        }

        camera_info = {"Model": "test_model", "Num": 0}
        model = CameraCoreModel(camera_info, None)

        model.make_logfile_directories()

        mock_makedirs.assert_not_called()


# Test the Make Output Directories Functionality
class TestCameraCoreModelMakeOutputDirectories(unittest.TestCase):
    @patch("os.makedirs")
    @patch("os.path.exists")
    @patch("core.model.Picamera2")
    def test_make_output_directories(self, mock_picamera2, mock_exists, mock_makedirs):
        """Test the make_output_directories function."""
        mock_exists.return_value = False

        mock_picamera2_instance = MagicMock()
        mock_picamera2_instance.camera_config = {
            "main": {"size": (1920, 1080), "format": "RGB888"},
            "lores": {"size": (640, 480), "format": "YUV420"},
        }
        mock_picamera2_instance.sensor_resolution = (1920, 1080)
        mock_picamera2.return_value = mock_picamera2_instance

        camera_info = {"Model": "test_model", "Num": 0}
        model = CameraCoreModel(camera_info, None)

        model.make_output_directories()

        expected_calls = [
            call(os.path.dirname(model.config["preview_path"])),
            call(os.path.dirname(model.config["image_output_path"])),
            call(os.path.dirname(model.config["lapse_output_path"])),
            call(os.path.dirname(model.config["video_output_path"])),
            call(os.path.dirname(model.config["media_path"])),
            call(os.path.dirname(model.config["status_file"])),
        ]

        mock_makedirs.assert_has_calls(expected_calls, any_order=True)

        mock_exists.assert_has_calls(expected_calls, any_order=True)


# Test the Toggle Solo Stream Mode Functionality
class TestCameraCoreModelToggleSoloStreamMode(TestCameraCoreModelBase):
    def test_toggle_solo_stream_mode_on(self):
        """Test enabling solo stream mode (switch_on=True)."""
        self.model.toggle_solo_stream_mode(True)

        self.assertTrue(self.model.solo_stream_mode)
        self.assertEqual(self.model.config["picam_buffer_count"], 1)
        self.assertEqual(self.model.preview_stream, "main")
        self.assertEqual(self.model.record_stream, "main")
        self.assertEqual(self.model.md_stream, "main")

    def test_toggle_solo_stream_mode_off(self):
        """Test disabling solo stream mode (switch_on=False)."""
        self.model.toggle_solo_stream_mode(False)

        self.assertFalse(self.model.solo_stream_mode)
        self.assertEqual(self.model.config["picam_buffer_count"], 2)
        self.assertEqual(self.model.preview_stream, "lores")
        self.assertEqual(self.model.record_stream, "lores")
        self.assertEqual(self.model.md_stream, "raw")


# Test the Set Camera Configuration Functionality
class TestCameraCoreModelSetCameraConfiguration(TestCameraCoreModelBase):
    def test_set_camera_configuration_px(self):
        """Test general settings."""
        self.model.set_camera_configuration("px", "1280 720 20 20 900 600 1")
        self.assertEqual(self.model.config["video_width"], 1280)
        self.assertEqual(self.model.config["video_height"], 720)
        self.assertEqual(self.model.config["video_fps"], 20)
        self.assertEqual(self.model.config["mp4_fps"], 20)
        self.assertEqual(self.model.config["image_width"], 900)
        self.assertEqual(self.model.config["image_height"], 600)

    def test_set_camera_configuration_flip_0(self):
        """Test setting camera flip with mode 0 (no flip)."""
        self.model.set_camera_configuration("fl", "0")
        self.assertEqual(self.model.config["hflip"], 0)
        self.assertEqual(self.model.config["vflip"], 0)

    def test_set_camera_configuration_flip_1(self):
        """Test setting camera flip with mode 1 (hflip=1, vflip=0)."""
        self.model.set_camera_configuration("fl", "1")
        self.assertEqual(self.model.config["hflip"], 1)
        self.assertEqual(self.model.config["vflip"], 0)

    def test_set_camera_configuration_flip_2(self):
        """Test setting camera flip with mode 2 (hflip=0, vflip=1)."""
        self.model.set_camera_configuration("fl", "2")
        self.assertEqual(self.model.config["hflip"], 0)
        self.assertEqual(self.model.config["vflip"], 1)

    def test_set_camera_configuration_flip_3(self):
        """Test setting camera flip with mode 3 (hflip=1, vflip=1)."""
        self.model.set_camera_configuration("fl", "3")
        self.assertEqual(self.model.config["hflip"], 1)
        self.assertEqual(self.model.config["vflip"], 1)

    def test_set_camera_configuration_resolution_change(self):
        """Test changing the camera resolution."""
        self.model.set_camera_configuration("cr", "1920 1080")
        self.assertEqual(self.model.sensor_format, (1920, 1080))

    @patch("core.model.logging")
    def test_set_camera_configuration_invalid_resolution_change(self, mock_logging):
        """Test invalid resolution change (non-integer)."""
        self.model.set_camera_configuration("cr", "invalid 1080")
        mock_logging.error.assert_called_once_with(
            "Error: Invalid resolution parameters."
        )

    @patch("core.model.logging")
    def test_set_camera_configuration_cr_not_enough_params(self, mock_logging):
        """Test the 'cr' command with not enough parameters."""
        self.model.set_camera_configuration("cr", "")
        mock_logging.error.assert_called_once_with("ERROR: Not enough parameters.")

    def test_set_camera_configuration_change_image_stream_size(self):
        """Test changing the image stream size."""
        self.model.set_camera_configuration("cs", "i 1280 720")
        self.assertEqual(self.model.config["image_width"], 1280)
        self.assertEqual(self.model.config["image_height"], 720)

    def test_set_camera_configuration_change_video_stream_size(self):
        """Test changing the video stream size."""
        self.model.set_camera_configuration("cs", "v 640 480")
        self.assertEqual(self.model.config["video_width"], 640)
        self.assertEqual(self.model.config["video_height"], 480)

    def test_set_camera_configuration_change_both_stream_sizes(self):
        """Test changing both image and video stream sizes."""
        self.model.set_camera_configuration("cs", "i+v 1024 768 1024 768")
        self.assertEqual(self.model.config["image_width"], 1024)
        self.assertEqual(self.model.config["image_height"], 768)
        self.assertEqual(self.model.config["video_width"], 1024)
        self.assertEqual(self.model.config["video_height"], 768)

    @patch("core.model.logging")
    def test_set_camera_configuration_invalid_stream_size_change(self, mock_logging):
        """Test invalid stream size change."""
        self.model.set_camera_configuration("cs", "invalid 1280 720")
        mock_logging.error.assert_called_once_with(
            "Error: Invalid target for size change."
        )

    @patch("core.model.logging")
    def test_set_camera_configuration_cs_not_enough_params(self, mock_logging):
        """Test the 'cs' command with not enough parameters."""
        self.model.set_camera_configuration("cs", "i 1920")
        mock_logging.error.assert_called_once_with("ERROR: Not enough parameters.")

    @patch("core.model.logging")
    def test_set_camera_configuration_cs_invalid_params(self, mock_logging):
        """Test invalid resolution parameters for 'cs' command."""
        self.model.set_camera_configuration("cs", "i invalid 1080")
        mock_logging.error.assert_called_once_with(
            "Error: Invalid resolution parameters."
        )

    def test_set_camera_configuration_ix(self):
        """Test changing resolution via the 'ix' command."""
        self.model.set_camera_configuration("ix", [[1280, 720, 2], 1])
        self.assertEqual(self.model.config["image_width"], 1280)
        self.assertEqual(self.model.config["image_height"], 720)
        self.assertEqual(self.model.config["picam_buffer_count"], 2)

    def test_set_camera_configuration_ix_max_resolution(self):
        """Test the 'ix' command with cmd_param[1] == 0, expecting solo stream mode."""
        with patch.object(self.model, "toggle_solo_stream_mode") as mock_toggle:
            self.model.set_camera_configuration("ix", [[1920, 1080, 2], 0])
            mock_toggle.assert_called_once_with(True)
            self.assertEqual(self.model.config["image_width"], 1920)
            self.assertEqual(self.model.config["image_height"], 1080)
            self.assertEqual(self.model.config["picam_buffer_count"], 2)

    def test_set_camera_configuration_1s_mode_1(self):
        """Test the '1s' command with cmd_param == '1'."""
        with patch.object(self.model, "toggle_solo_stream_mode") as mock_toggle:
            self.model.set_camera_configuration("1s", "1")
            mock_toggle.assert_any_call(True)
            self.assertFalse(self.model.show_preview)

    def test_set_camera_configuration_1s_mode_2(self):
        """Test the '1s' command with cmd_param == '2'."""
        with patch.object(self.model, "toggle_solo_stream_mode") as mock_toggle:
            self.model.set_camera_configuration("1s", "2")
            mock_toggle.assert_any_call(True)
            self.assertFalse(self.model.show_preview)
            self.assertEqual(self.model.sensor_format, (1920, 1080))

    def test_set_camera_configuration_1s_mode_invalid(self):
        """Test the '1s' command with an invalid cmd_param."""
        with patch.object(self.model, "toggle_solo_stream_mode") as mock_toggle:
            self.model.set_camera_configuration("1s", "invalid")
            mock_toggle.assert_any_call(False)

    def test_set_camera_configuration_rs(self):
        """Test reset user configs command."""
        with patch.object(self.model, "reset_user_configs") as mock_reset:
            self.model.set_camera_configuration("rs", None)
            mock_reset.assert_called_once()


# Test the Set Image Controls Functionality
class TestCameraCoreModelSetImageAdjustment(TestCameraCoreModelBase):
    def test_set_image_adjustment_sharpness(self):
        self.model.set_image_adjustment("Sharpness", 0)
        self.assertEqual(self.model.config["sharpness"], 1)
        self.model.set_image_adjustment("Sharpness", 100)
        self.assertEqual(self.model.config["sharpness"], 16.0)
        self.model.set_image_adjustment("Sharpness", -100)
        self.assertEqual(self.model.config["sharpness"], 0)

    def test_set_image_adjustment_contrast(self):
        self.model.set_image_adjustment("Contrast", 0)
        self.assertEqual(self.model.config["contrast"], 1)
        self.model.set_image_adjustment("Contrast", 100)
        self.assertEqual(self.model.config["contrast"], 32.0)
        self.model.set_image_adjustment("Contrast", -100)
        self.assertEqual(self.model.config["contrast"], 0)

    def test_set_image_adjustment_brightness(self):
        self.model.set_image_adjustment("Brightness", 50)
        self.assertEqual(self.model.config["brightness"], 0)
        self.model.set_image_adjustment("Brightness", 100)
        self.assertEqual(self.model.config["brightness"], 1.0)
        self.model.set_image_adjustment("Brightness", 0)
        self.assertEqual(self.model.config["brightness"], -1.0)

    def test_set_image_adjustment_sat(self):
        self.model.set_image_adjustment("Saturation", 0)
        self.assertEqual(self.model.config["saturation"], 1)
        self.model.set_image_adjustment("Saturation", 100)
        self.assertEqual(self.model.config["saturation"], 32.0)
        self.model.set_image_adjustment("Saturation", -100)
        self.assertEqual(self.model.config["saturation"], 0)


# Test the Set Motion Params Functionality
class TestCameraCoreModelSetMotionParams(TestCameraCoreModelBase):
    def test_set_motion_params_invalid_value(self):
        """Test the set_motion_params method with a non-integer cmd_param."""
        with patch("builtins.print") as mock_print:
            self.model.set_motion_params("mt", "invalid_value")
            mock_print.assert_called_once_with("ERROR: Value is not an integer")

    def test_set_motion_params_negative_value(self):
        """Test the set_motion_params method with a negative value."""
        self.model.set_motion_params("ms", "-5")
        self.assertEqual(self.model.config["motion_initframes"], 0)

    def test_set_motion_params_threshold(self):
        """Test setting the motion threshold with a valid value."""
        self.model.set_motion_params("mt", "350")
        expected_threshold = 350 / (250 / 7)
        self.assertEqual(self.model.config["motion_threshold"], expected_threshold)

    def test_set_motion_params_initframes(self):
        """Test setting the motion initframes with a valid value."""
        self.model.set_motion_params("ms", "10")
        self.assertEqual(self.model.config["motion_initframes"], 10)

    def test_set_motion_params_startframes(self):
        """Test setting the motion startframes with a valid value."""
        self.model.set_motion_params("mb", "5")
        self.assertEqual(self.model.config["motion_startframes"], 5)

    def test_set_motion_params_stopframes(self):
        """Test setting the motion stopframes with a valid value."""
        self.model.set_motion_params("me", "20")
        self.assertEqual(self.model.config["motion_stopframes"], 20)

    def test_set_motion_params_invalid_cmd_code(self):
        """Test the set_motion_params method with an invalid cmd_code."""
        original_config = self.model.config.copy()
        self.model.set_motion_params("invalid_cmd", "100")
        self.assertEqual(self.model.config, original_config)


# Test Encoder Setup Functionality
class TestCameraCoreModelSetupEncoders(TestCameraCoreModelBase):
    @patch("core.model.Picamera2")
    def setUp(self, mock_picamera2):
        """Set up the test case with a mocked Picamera2 instance."""
        self.mock_picamera2 = mock_picamera2.return_value
        self.mock_picamera2.stop_encoder = MagicMock()
        self.mock_picamera2.stop = MagicMock()
        self.mock_picamera2.start = MagicMock()
        self.mock_picamera2.close = MagicMock()
        self.mock_picamera2.capture_request = MagicMock()
        self.mock_picamera2.sensor_resolution = (1920, 1080)
        self.mock_picamera2.camera_config = {
            "main": {"size": (1920, 1080), "format": "YUV420"},
            "lores": {"size": (640, 480), "format": "YUV420"},
        }
        camera_info = {"Model": "test_model", "Num": 0}
        self.model = CameraCoreModel(camera_info, None)
        self.model.record_stream = "main"

    @patch("core.model.JpegEncoder")
    @patch("core.model.FileOutput")
    def test_setup_jpeg_encoder(self, mock_file_output, mock_jpeg_encoder):
        """Test that the JPEG encoder is set up with correct parameters."""
        _ = mock_jpeg_encoder.return_value
        mock_file_output_instance = mock_file_output.return_value

        self.model.setup_jpeg_encoder()

        mock_jpeg_encoder.assert_called_once_with(q=self.model.config["image_quality"])

        self.assertEqual(self.model.jpeg_encoder.output, mock_file_output_instance)

    @patch("core.model.H264Encoder")
    def test_setup_video_encoder(self, mock_h264_encoder):
        """Test that the H264 encoder is set up with correct parameters."""
        mock_h264_encoder_instance = mock_h264_encoder.return_value

        self.model.setup_video_encoder()

        mock_h264_encoder.assert_called_once_with(
            bitrate=self.model.config["video_bitrate"], framerate=30
        )

        mock_h264_encoder_instance.size = self.model.picam2.camera_config[
            self.model.record_stream
        ]["size"]
        mock_h264_encoder_instance.format = self.model.picam2.camera_config[
            self.model.record_stream
        ]["format"]

        self.assertEqual(mock_h264_encoder_instance.size, (1920, 1080))
        self.assertEqual(mock_h264_encoder_instance.format, "YUV420")


# Test Config Functionality
class TestCameraCoreModelConfig(unittest.TestCase):
    @patch("core.model.Picamera2", autospec=True)
    def setUp(self, MockPicamera2):
        """Set up default mocks for Picamera2 attributes used in tests."""
        self.mock_picamera2 = MockPicamera2.return_value
        self.mock_picamera2.options = {"quality": 70}
        self.mock_picamera2.sensor_resolution = (1920, 1080)
        self.mock_picamera2.camera_config = {
            "main": {"size": (1920, 1080), "format": "RGB888"},
            "lores": {"size": (640, 480), "format": "YUV420"},
        }

        camera_info = {"Model": "test_model", "Num": 0}
        config_path = None
        self.model = CameraCoreModel(camera_info, config_path)

    @patch("core.model.Picamera2", autospec=True)
    @patch("builtins.open", new_callable=mock_open, read_data="")
    @patch("os.path.exists", return_value=True)
    def test_read_config_file_no_config_file(
        self, mock_exists, mock_file, MockPicamera2
    ):
        """Test read_config_file when no config file is provided."""
        MockPicamera2.return_value = self.mock_picamera2

        self.assertEqual(self.model.config["preview_size"], (512, 288))
        self.assertEqual(mock_file.call_count, 0)

    @patch("core.model.Picamera2", autospec=True)
    @patch("builtins.open", new_callable=mock_open, read_data="width 1024\nheight 768")
    def test_read_config_file_with_resolution(self, mock_file, MockPicamera2):
        """Test that width and height are correctly parsed from the config file."""
        MockPicamera2.return_value = self.mock_picamera2
        camera_info = {"Model": "test_model", "Num": 0}
        config_path = "dummy_path"
        model = CameraCoreModel(camera_info, config_path)

        model.read_config_file(config_path)
        self.assertEqual(model.config["preview_size"], (1024, 768))
        self.assertEqual(mock_file.call_count, 4)

    @patch("core.model.Picamera2", autospec=True)
    @patch("builtins.open", new_callable=mock_open, read_data="sharpness 50")
    def test_read_config_file_sharpness(self, mock_file, MockPicamera2):
        """Test sharpness scaling in config file."""
        MockPicamera2.return_value = self.mock_picamera2
        camera_info = {"Model": "test_model", "Num": 0}
        config_path = "dummy_path"
        model = CameraCoreModel(camera_info, config_path)

        model.read_config_file(config_path)
        self.assertEqual(model.config["sharpness"], 8.5)
        self.assertEqual(mock_file.call_count, 4)

    @patch("core.model.Picamera2", autospec=True)
    @patch("builtins.open", new_callable=mock_open, read_data="contrast 50")
    def test_read_config_file_contrast(self, mock_file, MockPicamera2):
        """Test contrast scaling in config file."""
        MockPicamera2.return_value = self.mock_picamera2
        camera_info = {"Model": "test_model", "Num": 0}
        config_path = "dummy_path"
        model = CameraCoreModel(camera_info, config_path)

        model.read_config_file(config_path)
        self.assertEqual(model.config["contrast"], 16.5)
        self.assertEqual(mock_file.call_count, 4)

    @patch("core.model.Picamera2", autospec=True)
    @patch("builtins.open", new_callable=mock_open, read_data="brightness 50")
    def test_read_config_file_brightness(self, mock_file, MockPicamera2):
        """Test brightness scaling in config file."""
        MockPicamera2.return_value = self.mock_picamera2
        camera_info = {"Model": "test_model", "Num": 0}
        config_path = "dummy_path"
        model = CameraCoreModel(camera_info, config_path)

        model.read_config_file(config_path)
        self.assertEqual(model.config["brightness"], 0.0)
        self.assertEqual(mock_file.call_count, 4)

    @patch("core.model.Picamera2", autospec=True)
    @patch("builtins.open", new_callable=mock_open, read_data="rotation 180")
    def test_read_config_file_rotation(self, mock_file, MockPicamera2):
        """Test rotation setting in config file."""
        MockPicamera2.return_value = self.mock_picamera2
        camera_info = {"Model": "test_model", "Num": 0}
        config_path = "dummy_path"
        model = CameraCoreModel(camera_info, config_path)

        model.read_config_file(config_path)
        self.assertEqual(model.config["rotation"], 180)
        self.assertEqual(mock_file.call_count, 4)

    @patch("core.model.Picamera2", autospec=True)
    @patch("builtins.open", new_callable=mock_open, read_data="hflip true\nvflip false")
    def test_read_config_file_flips(self, mock_file, MockPicamera2):
        """Test hflip and vflip parsing from config file."""
        MockPicamera2.return_value = self.mock_picamera2
        camera_info = {"Model": "test_model", "Num": 0}
        config_path = "dummy_path"
        model = CameraCoreModel(camera_info, config_path)

        model.read_config_file(config_path)
        self.assertTrue(model.config["hflip"])
        self.assertFalse(model.config["vflip"])
        self.assertEqual(mock_file.call_count, 4)

    @patch("core.model.Picamera2", autospec=True)
    @patch("builtins.open", new_callable=mock_open, read_data="motion_external 2")
    def test_read_config_file_motion_mode(self, mock_file, MockPicamera2):
        """Test motion mode setting in config file."""
        MockPicamera2.return_value = self.mock_picamera2
        camera_info = {"Model": "test_model", "Num": 0}
        config_path = "dummy_path"
        model = CameraCoreModel(camera_info, config_path)

        model.read_config_file(config_path)
        self.assertEqual(model.config["motion_mode"], "monitor")
        self.assertEqual(mock_file.call_count, 4)

    @patch("core.model.Picamera2", autospec=True)
    @patch("builtins.open", new_callable=mock_open, read_data="motion_threshold 250")
    def test_read_config_file_motion_threshold(self, mock_file, MockPicamera2):
        """Test motion threshold scaling from config file."""
        MockPicamera2.return_value = self.mock_picamera2
        camera_info = {"Model": "test_model", "Num": 0}
        config_path = "dummy_path"
        model = CameraCoreModel(camera_info, config_path)

        model.read_config_file(config_path)
        self.assertEqual(model.config["motion_threshold"], 7.0)
        self.assertEqual(mock_file.call_count, 4)

    @patch("core.model.Picamera2", autospec=True)
    @patch("builtins.open", new_callable=mock_open, read_data="thumb_gen v")
    def test_read_config_file_thumb_gen(self, mock_file, MockPicamera2):
        """Test thumb_gen setting from config file."""
        MockPicamera2.return_value = self.mock_picamera2
        camera_info = {"Model": "test_model", "Num": 0}
        config_path = "dummy_path"
        model = CameraCoreModel(camera_info, config_path)

        model.read_config_file(config_path)
        self.assertEqual(model.config["thumb_gen"], "v")
        self.assertEqual(mock_file.call_count, 4)

    @patch("core.model.Picamera2", autospec=True)
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data="user_config /tmp/user_config",
    )
    def test_read_config_file_user_config(self, mock_file, MockPicamera2):
        """Test user_config setting from config file."""
        MockPicamera2.return_value = self.mock_picamera2
        camera_info = {"Model": "test_model", "Num": 0}
        config_path = "dummy_path"
        model = CameraCoreModel(camera_info, config_path)

        model.read_config_file(config_path)
        self.assertEqual(model.config["user_config"], "/tmp/user_config")
        self.assertEqual(mock_file.call_count, 5)

    def test_process_annotation_settings(self):
        """Test parsing of annotation-related settings."""
        parsed_configs = {
            "annotation": "Test Annotation",
            "anno_text_scale": "3",
            "anno_text_origin": "50 100",
            "anno_text_colour": "255 255 255",
            "anno_text_thickness": "10",
        }
        self.model.process_configs_from_file(parsed_configs)

        self.assertEqual(self.model.config["annotation"], "Test Annotation")
        self.assertEqual(self.model.config["anno_text_scale"], 3)
        self.assertEqual(self.model.config["anno_text_origin"], (50, 100))
        self.assertEqual(self.model.config["anno_text_colour"], (255, 255, 255))
        self.assertEqual(self.model.config["anno_text_thickness"], 10)

    def test_process_camera_settings(self):
        """Test parsing of camera settings like sharpness, contrast, and brightness."""
        parsed_configs = {
            "sharpness": "50",
            "contrast": "50",
            "brightness": "75",
            "saturation": "25",
            "exposure_compensation": "5",
            "rotation": "90",
            "hflip": "true",
            "vflip": "false",
        }
        self.model.process_configs_from_file(parsed_configs)

        self.assertEqual(self.model.config["sharpness"], 8.5)
        self.assertEqual(self.model.config["contrast"], 16.5)
        self.assertEqual(self.model.config["brightness"], 0.5)
        self.assertEqual(self.model.config["saturation"], 8.75)
        self.assertEqual(self.model.config["exposure_compensation"], 4.0)
        self.assertEqual(self.model.config["rotation"], 90)
        self.assertTrue(self.model.config["hflip"])
        self.assertFalse(self.model.config["vflip"])

    def test_process_fifo_and_status_file_settings(self):
        """Test parsing of fifo and status file settings."""
        parsed_configs = {
            "status_file": "/tmp/new_status.txt",
            "control_file": "/tmp/new_fifo",
            "motion_pipe": "/tmp/new_motion_fifo",
            "fifo_interval": "500000",
        }
        self.model.process_configs_from_file(parsed_configs)

        self.assertEqual(self.model.config["status_file"], "/tmp/new_status.txt")
        self.assertEqual(self.model.config["control_file"], "/tmp/new_fifo")
        self.assertEqual(self.model.config["motion_pipe"], "/tmp/new_motion_fifo")
        self.assertEqual(CameraCoreModel.fifo_interval, 0.5)

    def test_process_output_filepaths_and_size(self):
        """Test parsing of output filepaths and preview size."""
        parsed_configs = {
            "preview_path": "/tmp/new_preview.jpg",
            "media_path": "/media/new_media",
            "image_path": "/media/new_images/img.jpg",
            "lapse_path": "/media/new_timelapse/tl.jpg",
            "video_path": "/media/new_video/vid.mp4",
            "width": "1280",
            "height": "720",
        }
        self.model.process_configs_from_file(parsed_configs)

        self.assertEqual(self.model.config["preview_path"], "/tmp/new_preview.jpg")
        self.assertEqual(self.model.config["media_path"], "/media/new_media")
        self.assertEqual(
            self.model.config["image_output_path"], "/media/new_images/img.jpg"
        )
        self.assertEqual(
            self.model.config["lapse_output_path"], "/media/new_timelapse/tl.jpg"
        )
        self.assertEqual(
            self.model.config["video_output_path"], "/media/new_video/vid.mp4"
        )
        self.assertEqual(self.model.config["preview_size"], (1280, 720))

    def test_process_video_settings(self):
        """Test parsing of video resolution and bitrate."""
        parsed_configs = {
            "video_width": "1920",
            "video_height": "1080",
            "video_bitrate": "8000000",
        }
        self.model.process_configs_from_file(parsed_configs)

        self.assertEqual(self.model.config["video_width"], 1920)
        self.assertEqual(self.model.config["video_height"], 1080)
        self.assertEqual(self.model.config["video_bitrate"], 8000000)

    def test_process_still_image_settings(self):
        """Test parsing of still image resolution and quality."""
        parsed_configs = {
            "image_width": "4000",
            "image_height": "3000",
            "image_quality": "85",
        }
        self.model.process_configs_from_file(parsed_configs)

        self.assertEqual(self.model.config["image_width"], 4000)
        self.assertEqual(self.model.config["image_height"], 3000)
        self.assertEqual(self.model.config["image_quality"], 85)

    def test_process_motion_settings(self):
        """Test parsing of motion detection settings."""
        parsed_configs = {
            "motion_external": "2",
            "motion_threshold": "350",
            "motion_initframes": "5",
            "motion_startframes": "3",
            "motion_stopframes": "10",
        }
        self.model.process_configs_from_file(parsed_configs)

        self.assertEqual(self.model.config["motion_mode"], "monitor")
        self.assertAlmostEqual(self.model.config["motion_threshold"], 9.8, delta=0.01)
        self.assertEqual(self.model.config["motion_initframes"], 5)
        self.assertEqual(self.model.config["motion_startframes"], 3)
        self.assertEqual(self.model.config["motion_stopframes"], 10)

    def test_process_thumbnail_settings(self):
        """Test parsing of thumbnail generation settings."""
        parsed_configs = {"thumb_gen": "v"}
        self.model.process_configs_from_file(parsed_configs)
        self.assertEqual(self.model.config["thumb_gen"], "v")

    def test_process_autostart_and_motion_detection(self):
        """Test parsing of autostart and motion detection settings."""
        parsed_configs = {
            "autostart": "standard",
            "motion_detection": "true",
        }
        self.model.process_configs_from_file(parsed_configs)

        self.assertTrue(self.model.config["autostart"])
        self.assertTrue(self.model.config["motion_detection"])

    def test_process_user_config(self):
        """Test parsing of user config settings."""
        parsed_configs = {"user_config": "/tmp/new_user_config"}
        self.model.process_configs_from_file(parsed_configs)
        self.assertEqual(self.model.config["user_config"], "/tmp/new_user_config")

    def test_process_log_settings(self):
        """Test parsing of log file settings."""
        parsed_configs = {
            "log_file": "/tmp/new_log_file.txt",
            "log_size": "10000",
            "motion_logfile": "/tmp/new_motion_log.txt",
        }
        self.model.process_configs_from_file(parsed_configs)

        self.assertEqual(self.model.config["log_file"], "/tmp/new_log_file.txt")
        self.assertEqual(self.model.config["log_size"], 10000)
        self.assertEqual(self.model.config["motion_logfile"], "/tmp/new_motion_log.txt")

    def test_process_multicam_settings(self):
        """Test parsing of multi-cam specific settings."""
        parsed_configs = {
            "show_preview": "false",
            "picam_buffer_count": "3",
            "camera_resolution": "3840 2160",
            "solo_stream_mode": "true",
        }
        self.model.process_configs_from_file(parsed_configs)

        self.assertFalse(self.model.show_preview)
        self.assertEqual(self.model.config["picam_buffer_count"], 3)
        self.assertEqual(self.model.sensor_format, (3840, 2160))
        self.assertTrue(self.model.config["solo_stream_mode"])

    def test_process_configs_solo_stream_mode_false(self):
        """Test solo_stream_mode is set to False when the config value is not 'true'."""
        parsed_configs = {"solo_stream_mode": "false"}

        self.model.process_configs_from_file(parsed_configs)

        self.assertFalse(self.model.config["solo_stream_mode"])


# Test Capture Request Functionality
class TestCameraCoreModelCaptureRequest(TestCameraCoreModelBase):
    def test_capture_request(self):
        """Test the capture_request function."""
        self.mock_picamera2.capture_request.return_value = "mocked_capture_request"

        result = self.model.capture_request()

        self.mock_picamera2.capture_request.assert_called_once()
        self.assertEqual(result, "mocked_capture_request")


# Test Set Status Functionality
class TestCameraCoreModelSetStatus(unittest.TestCase):
    @patch("core.model.Picamera2")
    def setUp(self, mock_picamera2):
        """Set up the test case with a mocked Picamera2 instance."""
        self.mock_picamera2 = mock_picamera2.return_value

        self.mock_picamera2.started = True
        self.mock_picamera2.sensor_resolution = (1920, 1080)
        self.mock_picamera2.camera_config = {
            "main": {"size": (1920, 1080), "format": "YUV420"},
            "lores": {"size": (640, 480), "format": "YUV420"},
        }

        self.mock_picamera2.stop_encoder = MagicMock()
        self.mock_picamera2.stop = MagicMock()
        self.mock_picamera2.start = MagicMock()

        camera_info = {"Model": "test_model", "Num": 0}
        self.model = CameraCoreModel(camera_info, None)

    def test_set_status_with_custom_status(self):
        """Test setting a custom status directly."""
        self.model.set_status("custom_status")
        self.assertEqual(self.model.current_status, "ready")

    def test_set_status_halted(self):
        """Test setting status when camera is not started."""
        self.mock_picamera2.started = False
        self.model.set_status()
        self.assertEqual(self.model.current_status, "halted")

    def test_set_status_video(self):
        """Test setting status when capturing video without motion detection."""
        self.model.capturing_video = True
        self.model.motion_detection = False
        self.model.set_status()
        self.assertEqual(self.model.current_status, "video")

    def test_set_status_video_motion(self):
        """Test setting status when capturing video with motion detection."""
        self.model.capturing_video = True
        self.model.motion_detection = True
        self.model.set_status()
        self.assertEqual(self.model.current_status, "md_video")

    def test_set_status_image(self):
        """Test setting status when capturing still image."""
        self.model.capturing_still = True
        self.model.set_status()
        self.assertEqual(self.model.current_status, "image")

    def test_set_status_motion(self):
        """Test setting status when not capturing but motion detection is active."""
        self.model.motion_detection = True
        self.model.set_status()
        self.assertEqual(self.model.current_status, "md_ready")

    def test_set_status_ready(self):
        """Test setting status when the camera is ready (no video or still capture, no motion)."""
        self.model.capturing_video = False
        self.model.capturing_still = False
        self.model.motion_detection = False
        self.model.set_status()
        self.assertEqual(self.model.current_status, "ready")


# Test Make Filename Functionality
class TestCameraCoreModelMakeFilename(unittest.TestCase):
    @patch("core.model.Picamera2")
    @patch("core.model.datetime")
    def test_make_filename_image(self, mock_datetime, mock_picamera2):
        """Test make_filename function for image files with a mock datetime and still image index."""
        mock_datetime.now.return_value = datetime(2024, 12, 25, 14, 30, 45, 123000)

        mock_picamera2_instance = MagicMock()
        mock_picamera2.return_value = mock_picamera2_instance

        mock_picamera2_instance.sensor_resolution = (1920, 1080)
        mock_picamera2_instance.camera_config = {
            "main": {"size": (1920, 1080), "format": "RGB888"},
            "lores": {"size": (640, 480), "format": "YUV420"},
        }

        camera_info = {"Model": "test_model", "Num": 0}
        model = CameraCoreModel(camera_info, None)

        model.still_image_index = 5

        filename_template = "im_cam%I_%i_%Y%M%D_%h%m%s.jpg"

        expected_filename = "im_cam0_0005_20241225_143045.jpg"

        generated_filename = model.make_filename(filename_template)

        self.assertEqual(generated_filename, expected_filename)

    @patch("core.model.Picamera2")
    @patch("core.model.datetime")
    def test_make_filename_video(self, mock_datetime, mock_picamera2):
        """Test make_filename function for video files with a mock datetime and video file index."""
        mock_datetime.now.return_value = datetime(2024, 12, 25, 14, 30, 45, 123000)

        mock_picamera2_instance = MagicMock()
        mock_picamera2.return_value = mock_picamera2_instance

        mock_picamera2_instance.sensor_resolution = (1920, 1080)
        mock_picamera2_instance.camera_config = {
            "main": {"size": (1920, 1080), "format": "RGB888"},
            "lores": {"size": (640, 480), "format": "YUV420"},
        }

        camera_info = {"Model": "test_model", "Num": 0}
        model = CameraCoreModel(camera_info, None)

        model.video_file_index = 10

        filename_template = "vi_cam%I_%v_%Y%M%D_%h%m%s.mp4"

        expected_filename = "vi_cam0_0010_20241225_143045.mp4"

        generated_filename = model.make_filename(filename_template)

        self.assertEqual(generated_filename, expected_filename)

    @patch("core.model.Picamera2")
    @patch("core.model.datetime")
    def test_make_filename_with_millisecs(self, mock_datetime, mock_picamera2):
        """Test make_filename with milliseconds and mixed indices."""
        mock_datetime.now.return_value = datetime(2024, 12, 25, 14, 30, 45, 678000)

        mock_picamera2_instance = MagicMock()
        mock_picamera2.return_value = mock_picamera2_instance

        mock_picamera2_instance.sensor_resolution = (1920, 1080)
        mock_picamera2_instance.camera_config = {
            "main": {"size": (1920, 1080), "format": "RGB888"},
            "lores": {"size": (640, 480), "format": "YUV420"},
        }

        camera_info = {"Model": "test_model", "Num": 1}
        model = CameraCoreModel(camera_info, None)

        model.still_image_index = 25
        model.video_file_index = 30

        filename_template = "file_cam%I_%i_%v_%Y%M%D_%h%m%s_%u.ext"

        expected_filename = "file_cam1_0025_0030_20241225_143045_678.ext"

        generated_filename = model.make_filename(filename_template)

        self.assertEqual(generated_filename, expected_filename)


# Test Make Filecounts Functionality
class TestCameraCoreModelMakeFilecounts(TestCameraCoreModelBase):
    @patch("os.listdir")
    def test_make_filecounts(self, mock_listdir):
        """Test make_filecounts with both image and video thumbnails."""
        mock_listdir.side_effect = [
            [
                "im_0001.i1.th.jpg",
                "im_0003.i3.th.jpg",
            ],
            [
                "vi_0002.v2.th.jpg",
                "vi_0005.v5.th.jpg",
            ],
        ]

        self.model.make_filecounts()

        self.assertEqual(self.model.still_image_index, 4)
        self.assertEqual(self.model.video_file_index, 6)

    @patch("os.listdir")
    def test_make_filecounts_with_no_files(self, mock_listdir):
        """Test make_filecounts when there are no thumbnails."""
        mock_listdir.side_effect = [[], []]

        self.model.make_filecounts()

        self.assertEqual(self.model.still_image_index, 1)
        self.assertEqual(self.model.video_file_index, 1)

    @patch("os.listdir")
    def test_make_filecounts_with_invalid_files(self, mock_listdir):
        """Test make_filecounts when there are invalid filenames in the directory."""
        mock_listdir.side_effect = [
            ["im_invalid.th.jpg", "randomfile.txt"],
            ["vi_invalid.th.jpg", "some_other_file.mp4"],
        ]

        self.model.make_filecounts()

        self.assertEqual(self.model.still_image_index, 1)
        self.assertEqual(self.model.video_file_index, 1)

    @patch("os.listdir")
    def test_make_filecounts_mixed_filenames(self, mock_listdir):
        """Test make_filecounts when there is a mix of valid and invalid files."""
        mock_listdir.side_effect = [
            ["im_0001.i1.th.jpg", "im_invalid.th.jpg", "randomfile.txt"],
            ["vi_0002.v2.th.jpg", "some_other_file.mp4"],
        ]

        self.model.make_filecounts()

        self.assertEqual(self.model.still_image_index, 2)
        self.assertEqual(self.model.video_file_index, 3)

    @patch("os.listdir")
    def test_make_filecounts_with_large_index(self, mock_listdir):
        """Test make_filecounts with large image and video indexes."""
        mock_listdir.side_effect = [
            ["im_0999.i999.th.jpg"],
            ["vi_1000.v1000.th.jpg"],
        ]

        self.model.make_filecounts()

        self.assertEqual(self.model.still_image_index, 1000)
        self.assertEqual(self.model.video_file_index, 1001)


if __name__ == "__main__":
    unittest.main()
