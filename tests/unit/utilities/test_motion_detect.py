import unittest
from unittest.mock import patch, mock_open, MagicMock
import os
from datetime import datetime
from utilities.motion import (  # type: ignore
    setup_motion_pipe,
    print_to_motion_log,
    send_motion_command,
)


class TestMotionDetect(unittest.TestCase):
    @patch("os.makedirs")
    @patch("os.path.exists")
    @patch("os.mkfifo")
    def test_setup_motion_pipe_creates_directory_and_fifo(
        self, mock_mkfifo, mock_exists, mock_makedirs
    ):
        mock_exists.side_effect = [False, False]
        setup_motion_pipe("/fake/path/to/pipe")
        mock_makedirs.assert_called_once_with("/fake/path/to")
        mock_mkfifo.assert_called_once_with("/fake/path/to/pipe", 0o6666)

    @patch("os.makedirs")
    @patch("os.path.exists")
    @patch("os.mkfifo")
    def test_setup_motion_pipe_fifo_exists(
        self, mock_mkfifo, mock_exists, mock_makedirs
    ):
        mock_exists.side_effect = [True, False]
        setup_motion_pipe("/fake/path/to/pipe")
        mock_makedirs.assert_not_called()
        mock_mkfifo.assert_called_once_with("/fake/path/to/pipe", 0o6666)

    @patch("os.makedirs")
    @patch("os.path.exists")
    @patch("os.mkfifo")
    def test_setup_motion_pipe_directory_exists(
        self, mock_mkfifo, mock_exists, mock_makedirs
    ):
        mock_exists.side_effect = [True, True]
        setup_motion_pipe("/fake/path/to/pipe")
        mock_makedirs.assert_not_called()
        mock_mkfifo.assert_not_called()

    @patch("os.makedirs")
    @patch("os.path.exists")
    @patch("os.mkfifo")
    def test_setup_motion_pipe_directory_and_fifo_exist(
        self, mock_mkfifo, mock_exists, mock_makedirs
    ):
        mock_exists.side_effect = [True, True]
        setup_motion_pipe("/fake/path/to/pipe")
        mock_makedirs.assert_not_called()
        mock_mkfifo.assert_not_called()

    @patch("builtins.open", new_callable=mock_open)
    @patch("utilities.motion.datetime")
    def test_print_to_motion_log(self, mock_datetime, mock_open):
        mock_datetime.now.return_value = datetime(2023, 1, 1, 12, 0, 0)
        print_to_motion_log("/fake/path/to/log", "Test message")
        mock_open.assert_called_once_with("/fake/path/to/log", "a")
        mock_open().write.assert_called_once_with(
            "{2023/01/01 12:00:00} Test message\n"
        )

    @patch("os.open")
    @patch("os.fdopen")
    def test_send_motion_command(self, mock_fdopen, mock_open):
        mock_open.return_value = 3  # File descriptor
        mock_file = MagicMock()
        mock_fdopen.return_value = mock_file

        send_motion_command("/fake/path/to/pipe", "1")
        mock_open.assert_called_once_with(
            "/fake/path/to/pipe", os.O_RDWR | os.O_NONBLOCK, 0o666
        )
        mock_fdopen.assert_called_once_with(3, "w")
        mock_file.write.assert_called_once_with("1")
        mock_file.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
