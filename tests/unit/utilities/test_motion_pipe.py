import os
from unittest.mock import patch
from utilities.motion import setup_motion_pipe, send_motion_command  # type: ignore


@patch("os.mkfifo")
@patch("os.open")
@patch("os.fdopen")
def test_setup_motion_pipe(mock_fdopen, mock_open, mock_mkfifo):
    # Test setting up a FIFO path
    setup_motion_pipe("/tmp/motion_fifo")
    send_motion_command("/tmp/motion_fifo", "1")

    # Assert that the FIFO file was created and opened
    mock_mkfifo.assert_called_once_with("/tmp/motion_fifo", 0o6666)
    mock_open.assert_called_once_with(
        "/tmp/motion_fifo", os.O_RDWR | os.O_NONBLOCK, 0o666
    )
