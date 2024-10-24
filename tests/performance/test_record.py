import pytest
import time
from concurrent.futures import ThreadPoolExecutor
from core.process import CameraCoreModel  # type: ignore
from utilities.record import start_recording, stop_recording  # type: ignore


@pytest.fixture(scope="function")
def camera():
    """Fixture to set up the real camera instance for all tests in the module."""
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
    """Fixture to set up both cameras for multi-camera tests."""
    from picamera2 import Picamera2

    all_cameras = Picamera2.global_camera_info()

    if len(all_cameras) < 2:
        pytest.fail("At least two cameras are required for multi-camera tests")

    cameras = [CameraCoreModel(info, config_path=None) for info in all_cameras]

    yield cameras

    for cam in cameras:
        cam.teardown()


# Test Video Recording Performance
class TestVideoRecordingPerformance:
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
            (8000, 6000),  # Ultra-high resolution for ov64a40
            (9248, 6944),  # Max supported resolution for ov64a40
        ],
    )
    def test_video_recording_all_resolutions(self, camera, resolution):
        """Test video recording for all supported resolutions across imx219 and ov64a40 cameras."""
        camera.config["video_width"], camera.config["video_height"] = resolution

        start_time = time.time()
        start_recording(camera)
        time.sleep(2)
        stop_recording(camera)
        recording_time = time.time() - start_time

        print(f"Recorded video at {resolution} in {recording_time} seconds")
        assert (
            recording_time < 3.0
        ), f"Video recording took too long at resolution {resolution}"

    def test_concurrent_video_recording_performance(self, cameras):
        """Test the performance of recording multiple videos concurrently."""

        def record_video_concurrently(cam):
            start_recording(cam)
            time.sleep(2)
            stop_recording(cam)

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(record_video_concurrently, cam) for cam in cameras
            ]
            results = [f.result() for f in futures]

        assert all(result is None for result in results), "Some video recordings failed"

    @pytest.mark.parametrize("brightness", [0, 50, 100])
    def test_video_recording_in_low_light_conditions(self, camera, brightness):
        """Test the video recording performance under different brightness settings."""
        camera.config["brightness"] = brightness

        start_time = time.time()
        start_recording(camera)
        time.sleep(2)
        stop_recording(camera)
        recording_time = time.time() - start_time

        print(
            f"Video recording in brightness {brightness} took {recording_time} seconds"
        )
        assert (
            recording_time < 3.0
        ), "Video recording took too long in low light conditions"

    def test_video_file_io_performance(self, camera):
        """Test if the file I/O for saving the video affects performance."""
        start_time = time.time()
        start_recording(camera)
        time.sleep(2)
        stop_recording(camera)
        total_time = time.time() - start_time

        print(f"Total time for recording and file save: {total_time} seconds")
        assert total_time < 3.0, "File I/O caused a performance bottleneck"
