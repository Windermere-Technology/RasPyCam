import threading
import time
import os
from picamera2.previews.null_preview import NullPreview
import pytest


def pytest_configure(config):
    """Monkey patch the NullPreview class to handle the DeprecationWarning."""

    def patched_start(self, picam2):
        self.picam2 = picam2
        picam2.attach_preview(self)
        self._started.clear()
        self._abort.clear()

        self.thread = threading.Thread(target=self.thread_func, args=(picam2,))
        self.thread.daemon = True
        self.thread.start()
        self._started.wait()

    NullPreview.start = patched_start


# Hook to measure and print test duration only for tests in the 'performance' folder
@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_call(item):
    """Hook to time the execution of each test and print the duration for 'performance' folder tests."""
    # Get the file path of the current test
    test_file_path = os.path.abspath(item.fspath)

    # Check if the test is in the 'performance' folder
    if "tests/performance" in test_file_path:
        start_time = time.time()
        yield  # Run the actual test
        end_time = time.time()
        duration = end_time - start_time
        print(f"Test {item.name} in {test_file_path} took {duration:.5f} seconds")
    else:
        yield  # Run the actual test without timing
