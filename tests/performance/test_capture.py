import pytest
import time
from concurrent.futures import ThreadPoolExecutor
from core.process import CameraCoreModel  # type: ignore
from utilities.capture import capture_still_image, capture_stitched_image  # type: ignore

import sys

sys.path.append("..")


@pytest.fixture(scope="function")
def camera():
    """Fixture to set up the real camera instance for all test functions."""
    from picamera2 import Picamera2

    all_cameras = Picamera2.global_camera_info()

    if not all_cameras:
        pytest.fail("No cameras found")

    camera_info = all_cameras[0]
    camera = CameraCoreModel(camera_info, config_path=None)

    yield camera

    camera.teardown()


@pytest.fixture(scope="function")
def cameras():
    """Fixture to set up both cameras for stitching tests."""
    from picamera2 import Picamera2

    all_cameras = Picamera2.global_camera_info()

    if len(all_cameras) < 2:
        pytest.fail("At least two cameras are required for stitching tests")

    cameras = {}
    for info in all_cameras:
        cameras[info["Num"]] = CameraCoreModel(info, config_path=None)

    yield cameras

    for cam in cameras.values():
        cam.teardown()


# Test Capture Performance
class TestCapturePerformance:
    @pytest.mark.parametrize(
        "resolution",
        [
            (640, 480),  # Low resolution for imx219 and ov64a40
            (1640, 1232),  # Medium resolution for imx219
            (1920, 1080),  # Full HD for both cameras
            (3280, 2464),  # Max supported resolution for imx219
            (2312, 1736),  # Medium resolution for ov64a40
            (3840, 2160),  # 4K for ov64a40
            (4624, 3472),  # High resolution for ov64a40
            # (8000, 6000),  # Ultra-high resolution for ov64a40
            # (9248, 6944),  # Max supported resolution for ov64a40
        ],
    )
    def test_capture_image_all_resolutions(self, camera, resolution):
        """Test capture for all supported resolutions across imx219 and ov64a40 cameras."""
        camera.config["image_width"], camera.config["image_height"] = resolution
        camera.sensor_format = resolution
        camera.picam2.stop()
        camera.build_configuration_object()
        camera.restart()

        start_time = time.time()
        capture_still_image(camera)
        capture_time = time.time() - start_time

        print(f"Captured image at {resolution} in {capture_time} seconds")
        assert capture_time < 3.0, f"Capture took too long for resolution {resolution}"

    def test_concurrent_capture_performance(self, camera):
        """Test the performance of capturing multiple images concurrently."""

        def capture_image_concurrently():
            capture_still_image(camera)

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(capture_image_concurrently) for _ in range(5)]
            results = [f.result() for f in futures]

        assert all(result is None for result in results), "Some captures failed"

    @pytest.mark.parametrize("brightness", [0, 50, 100])
    def test_capture_in_low_light_conditions(self, camera, brightness):
        """Test the capture performance under different brightness settings."""
        camera.config["brightness"] = brightness
        camera.picam2.set_controls({"Brightness": camera.config["brightness"]})

        start_time = time.time()
        capture_still_image(camera)
        capture_time = time.time() - start_time

        print(f"Capture in brightness {brightness} took {capture_time} seconds")
        assert capture_time < 2.5, "Capture took too long in low light conditions"

    def test_capture_file_io_performance(self, camera):
        """Test if the file I/O for saving the image affects capture performance."""
        start_time = time.time()
        capture_still_image(camera)
        total_time = time.time() - start_time

        print(f"Total time for capture and file save: {total_time} seconds")
        assert total_time < 3.0, "File I/O caused a performance bottleneck"


# Test Image Stitching Performance
class TestImageStitchingPerformance:
    @pytest.mark.parametrize("axis", [0, 1])
    def test_capture_stitched_image(self, cameras, axis):
        """Test the capture_stitched_image function for both horizontal and vertical stitching."""
        start_time = time.time()
        capture_stitched_image(0, cameras, axis)
        capture_time = time.time() - start_time

        print(f"Stitched image captured along axis {axis} in {capture_time} seconds")
        assert capture_time < 5.0, f"Stitching took too long on axis {axis}"

    @pytest.mark.parametrize(
        "resolutions",
        [
            # [(3280, 2464), (9248, 6944)],  # Max resolutions for imx219 and ov64a40
            [(1920, 1080), (1920, 1080)],  # Full HD resolutions
            [(3840, 2160), (3840, 2160)],  # 4K resolutions
        ],
    )
    def test_capture_stitched_image_different_resolutions(self, cameras, resolutions):
        """Test stitching of images at different resolutions."""
        print(cameras)
        (
            cameras[0].config["image_width"],
            cameras[0].config["image_height"],
        ) = resolutions[0]
        cameras[0].sensor_format = resolutions[0]
        (
            cameras[1].config["image_width"],
            cameras[1].config["image_height"],
        ) = resolutions[1]
        cameras[1].sensor_format = resolutions[1]
        for cam in cameras.values():
            cam.picam2.stop()
            cam.build_configuration_object()
            cam.restart()

        start_time = time.time()
        capture_stitched_image(0, cameras, 0)
        capture_time = time.time() - start_time

        print(f"Stitched image at resolutions {resolutions} in {capture_time} seconds")
        assert capture_time < 6.0, "Stitching took too long for different resolutions"
