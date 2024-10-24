import unittest
from unittest.mock import patch, MagicMock, call
import os
import threading
import signal
import time
from core.process import (
    on_sigint_sigterm,
    update_status_file,
    setup_fifo,
    parse_incoming_commands,
    make_cmd_lists,
    read_pipe,
    pause_preview_md_threads,
    set_previews,
    show_preview,
    start_preview_md_threads,
    execute_all_commands,
    stop_all_cameras,
    execute_command,
)
from core.model import CameraCoreModel


class TestProcess(unittest.TestCase):
    @patch("builtins.print")
    def test_on_sigint_sigterm(self, mock_print):
        # Set process_running to True initially
        CameraCoreModel.process_running = True

        # Call the signal handler
        on_sigint_sigterm(signal.SIGINT, None)

        # Check if process_running is set to False
        self.assertFalse(CameraCoreModel.process_running)

        # Check if the correct signal was printed
        mock_print.assert_any_call("Received signal: ")
        mock_print.assert_any_call(signal.SIGINT)

    @patch("os.makedirs")
    @patch("os.path.exists", return_value=False)
    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    def test_update_status_file_directory_creation(
        self, mock_open, mock_exists, mock_makedirs
    ):
        model = MagicMock()
        model.config = {"status_file": "/tmp/status.txt"}
        model.current_status = "status"

        update_status_file(model)

        # Check if os.makedirs was called since the directory does not exist
        mock_makedirs.assert_called_once_with("/tmp")
        mock_exists.assert_called_once_with("/tmp")
        mock_open.assert_called_once_with("/tmp/status.txt", "w")
        mock_open().write.assert_called_once_with("status")

    @patch("os.makedirs")
    @patch("os.path.exists", return_value=True)
    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    def test_update_status_file_directory_exists(
        self, mock_open, mock_exists, mock_makedirs
    ):
        model = MagicMock()
        model.config = {"status_file": "/tmp/status.txt"}
        model.current_status = "status"

        update_status_file(model)

        # Check if os.makedirs was not called since the directory exists
        mock_makedirs.assert_not_called()
        mock_exists.assert_called_once_with("/tmp")
        mock_open.assert_called_once_with("/tmp/status.txt", "w")
        mock_open().write.assert_called_once_with("status")

    @patch("os.makedirs")
    @patch("os.path.exists", return_value=False)
    @patch("os.mkfifo")
    @patch("os.open")
    @patch("os.read", side_effect=BlockingIOError)
    def test_setup_fifo_directory_creation(
        self, mock_read, mock_open, mock_mkfifo, mock_exists, mock_makedirs
    ):
        path = "/tmp/fifo"
        result = setup_fifo(path)

        # Check if os.makedirs was called since the directory does not exist
        mock_makedirs.assert_called_once_with("/tmp")
        mock_exists.assert_any_call("/tmp")
        mock_exists.assert_any_call("/tmp/fifo")

        # Print the actual mode value received by os.mkfifo for debugging
        print(f"Actual mode value received by os.mkfifo: {mock_mkfifo.call_args}")

        mock_mkfifo.assert_called_once_with("/tmp/fifo", 3510)  # Correct the mode value
        mock_open.assert_called_once_with(
            "/tmp/fifo", os.O_RDONLY | os.O_NONBLOCK, 0o666
        )
        mock_read.assert_called_once_with(
            CameraCoreModel.fifo_fd, CameraCoreModel.MAX_COMMAND_LEN
        )
        self.assertFalse(result)

    @patch("os.makedirs")
    @patch("os.path.exists", return_value=True)
    @patch("os.mkfifo")
    @patch("os.open")
    @patch("os.read", return_value=b"")
    def test_setup_fifo_directory_exists(
        self, mock_read, mock_open, mock_mkfifo, mock_exists, mock_makedirs
    ):
        path = "/tmp/fifo"
        result = setup_fifo(path)

        # Check if os.makedirs was called since the directory exists
        mock_makedirs.assert_not_called()
        mock_exists.assert_any_call("/tmp")
        mock_exists.assert_any_call("/tmp/fifo")
        mock_mkfifo.assert_not_called()
        mock_open.assert_called_once_with(
            "/tmp/fifo", os.O_RDONLY | os.O_NONBLOCK, 0o666
        )
        mock_read.assert_called_once_with(
            CameraCoreModel.fifo_fd, CameraCoreModel.MAX_COMMAND_LEN
        )
        self.assertTrue(result)

    def test_make_cmd_lists_single_command_no_params(self):
        CameraCoreModel.VALID_COMMANDS = ["ca", "cb", "cc"]
        result = make_cmd_lists("[ca]")
        self.assertEqual(result, (["ca"], [""]))

    def test_make_cmd_lists_single_command_with_params(self):
        CameraCoreModel.VALID_COMMANDS = ["ca", "cb", "cc"]
        result = make_cmd_lists("[ca] param1")
        self.assertEqual(result, (["ca"], ["param1"]))

    def test_make_cmd_lists_multiple_commands_no_params(self):
        CameraCoreModel.VALID_COMMANDS = ["ca", "cb", "cc"]
        result = make_cmd_lists("[ca, cb, cc]")
        self.assertEqual(result, (["ca", "cb", "cc"], ["", "", ""]))

    def test_make_cmd_lists_multiple_commands_with_params(self):
        CameraCoreModel.VALID_COMMANDS = ["ca", "cb", "cc"]
        result = make_cmd_lists("[ca, cb, cc] [param1, param2, param3]")
        self.assertEqual(result, (["ca", "cb", "cc"], ["param1", " param2", " param3"]))

    def test_make_cmd_lists_invalid_command(self):
        CameraCoreModel.VALID_COMMANDS = ["ca", "cb", "cc"]
        result = make_cmd_lists("[ca, cd]")
        self.assertFalse(result)

    def test_make_cmd_lists_no_closing_bracket(self):
        CameraCoreModel.VALID_COMMANDS = ["ca", "cb", "cc"]
        result = make_cmd_lists("[ca, cb")
        self.assertFalse(result)

    def test_make_cmd_lists_escaped_commas_in_params(self):
        CameraCoreModel.VALID_COMMANDS = ["ca", "cb", "cc"]
        result = make_cmd_lists("[ca, cb] [param1, param2\\/param3]")
        self.assertEqual(result, (["ca", "cb"], ["param1", " param2\\/param3"]))

    def test_make_cmd_lists_more_commands_than_params(self):
        CameraCoreModel.VALID_COMMANDS = ["ca", "cb", "cc"]
        result = make_cmd_lists("[ca, cb, cc] [param1, param2]")
        self.assertEqual(result, (["ca", "cb", "cc"], ["param1", " param2", ""]))

    def test_make_cmd_lists_more_params_than_commands(self):
        CameraCoreModel.VALID_COMMANDS = ["ca", "cb"]
        result = make_cmd_lists("[ca, cb] [param1, param2, param3]")
        self.assertEqual(result, (["ca", "cb"], ["param1", " param2", " param3"]))

    def test_make_cmd_lists_blank_command(self):
        CameraCoreModel.VALID_COMMANDS = ["ca", "cb", "cc"]
        result = make_cmd_lists("[ca, , cc] [param1, , param3]")
        self.assertEqual(result, (["ca", "", "cc"], ["param1", " ", " param3"]))

    @patch("os.read")
    def test_read_pipe_valid_command(self, mock_read):
        # Mock the read function to return a valid command
        mock_read.return_value = b"ca param1"

        # Call the function
        result = read_pipe(0)

        # Check if the result is as expected
        self.assertEqual(result, ("ca", "param1"))

    @patch("os.read")
    def test_read_pipe_invalid_command(self, mock_read):
        # Mock the read function to return an invalid command
        mock_read.return_value = b"invalid_command"

        # Call the function
        result = read_pipe(0)

        # Check if the result is False
        self.assertFalse(result)

    @patch("os.read")
    def test_read_pipe_bracket_command(self, mock_read):
        # Mock the read function to return an invalid command
        mock_read.return_value = b"[ca,cb,cc] [param1,param2,param3]"
        result = read_pipe(0)
        # Check if the result is False
        self.assertEqual(result, (["ca", "cb", "cc"], ["param1", "param2", "param3"]))

    @patch("os.read")
    def test_read_pipe_empty_command(self, mock_read):
        # Mock the read function to return an empty command
        mock_read.return_value = b""

        # Call the function
        result = read_pipe(0)

        # Check if the result is False
        self.assertFalse(result)

        # Existing code...

    @patch("core.process.show_preview")
    @patch("core.process.motion_detection_thread")
    def test_pause_preview_md_threads(
        self, mock_motion_detection_thread, mock_show_preview
    ):
        # Mock the CameraCoreModel and its attributes
        CameraCoreModel.main_camera = "main_cam"
        cams = {"main_cam": MagicMock()}
        threads = [
            MagicMock(is_alive=MagicMock(return_value=True)),
            MagicMock(is_alive=MagicMock(return_value=False)),
        ]

        # Call the function
        pause_preview_md_threads(cams, threads)

        # Check if the main camera's status was set to "halted"
        self.assertEqual(cams["main_cam"].current_status, "halted")

        # Check if the main camera's status was updated
        cams["main_cam"].set_status.assert_called_once()

        # Check if new threads were created and added to the list
        self.assertEqual(len(threads), 2)
        self.assertIsInstance(threads[0], threading.Thread)
        self.assertIsInstance(threads[1], threading.Thread)

    @patch("core.model.CameraCoreModel.preview_dict_lock", new_callable=threading.Lock)
    def test_set_previews(self, mock_lock):
        # Mock the CameraCoreModel and its attributes
        CameraCoreModel.show_previews = {}
        cams = {
            0: MagicMock(show_preview=True),
            1: MagicMock(show_preview=False),
            2: MagicMock(show_preview=True),
        }

        # Call the function
        set_previews(cams)

        # Check if the show_previews dictionary was updated correctly
        self.assertEqual(CameraCoreModel.show_previews, {0: True, 1: False, 2: True})

    @patch("core.model.CameraCoreModel.preview_dict_lock", new_callable=threading.Lock)
    def test_set_previews_empty_cams(self, mock_lock):
        # Mock the CameraCoreModel and its attributes
        CameraCoreModel.show_previews = {}
        cams = {}

        # Call the function
        set_previews(cams)

        # Check if the show_previews dictionary remains empty
        self.assertEqual(CameraCoreModel.show_previews, {})

    @patch("core.process.generate_preview")
    def test_show_preview_running(self, mock_generate_preview):
        # Mock the CameraCoreModel and its attributes
        CameraCoreModel.main_camera = "main_cam"
        cams = {"main_cam": MagicMock(current_status="running")}

        # Run the show_preview function in a separate thread to simulate continuous execution
        preview_thread = threading.Thread(target=show_preview, args=(cams,))
        preview_thread.start()

        # Allow some time for the thread to run
        time.sleep(0.1)

        # Set the camera status to "halted" to stop the loop
        cams["main_cam"].current_status = "halted"

        # Wait for the thread to finish
        preview_thread.join()

        # Check if generate_preview was called at least once
        self.assertTrue(mock_generate_preview.called)

    @patch("core.process.generate_preview")
    def test_show_preview_halted(self, mock_generate_preview):
        # Mock the CameraCoreModel and its attributes
        CameraCoreModel.main_camera = "main_cam"
        cams = {"main_cam": MagicMock(current_status="halted")}

        # Run the show_preview function
        show_preview(cams)

        # Check if generate_preview was never called
        mock_generate_preview.assert_not_called()

    @patch("core.process.read_pipe")
    @patch("time.sleep", return_value=None)  # To avoid actual sleep during the test
    def test_parse_incoming_commands_valid_command(self, mock_sleep, mock_read_pipe):
        # Mock the CameraCoreModel and its attributes
        CameraCoreModel.process_running = True
        CameraCoreModel.fifo_fd = 1
        CameraCoreModel.command_queue = []
        CameraCoreModel.cmd_queue_lock = threading.Lock()
        CameraCoreModel.fifo_interval = 0.1

        # Mock the read_pipe function to return a valid command
        mock_read_pipe.return_value = ("ca", "param1")

        # Run the parse_incoming_commands function in a separate thread
        command_thread = threading.Thread(target=parse_incoming_commands)
        command_thread.start()

        # Allow some time for the thread to run
        time.sleep(0.2)

        # Stop the loop
        CameraCoreModel.process_running = False

        # Wait for the thread to finish
        command_thread.join()

        # Check if the command was added to the command queue
        self.assertIn(("ca", "param1"), CameraCoreModel.command_queue)

    @patch("core.process.read_pipe")
    @patch("time.sleep", return_value=None)  # To avoid actual sleep during the test
    def test_parse_incoming_commands_invalid_command(self, mock_sleep, mock_read_pipe):
        # Mock the CameraCoreModel and its attributes
        CameraCoreModel.process_running = True
        CameraCoreModel.fifo_fd = 1
        CameraCoreModel.command_queue = []
        CameraCoreModel.cmd_queue_lock = threading.Lock()
        CameraCoreModel.fifo_interval = 0.1

        # Mock the read_pipe function to return an invalid command
        mock_read_pipe.return_value = False

        # Run the parse_incoming_commands function in a separate thread
        command_thread = threading.Thread(target=parse_incoming_commands)
        command_thread.start()

        # Allow some time for the thread to run
        time.sleep(0.2)

        # Stop the loop
        CameraCoreModel.process_running = False

        # Wait for the thread to finish
        command_thread.join()

        # Check if the command queue is still empty
        self.assertEqual(CameraCoreModel.command_queue, [])

    @patch("core.process.read_pipe")
    @patch("time.sleep", return_value=None)  # To avoid actual sleep during the test
    def test_parse_incoming_commands_no_fifo_fd(self, mock_sleep, mock_read_pipe):
        # Mock the CameraCoreModel and its attributes
        CameraCoreModel.process_running = True
        CameraCoreModel.fifo_fd = None
        CameraCoreModel.command_queue = []
        CameraCoreModel.cmd_queue_lock = threading.Lock()
        CameraCoreModel.fifo_interval = 0.1

        # Run the parse_incoming_commands function in a separate thread
        command_thread = threading.Thread(target=parse_incoming_commands)
        command_thread.start()

        # Allow some time for the thread to run
        time.sleep(0.2)

        # Stop the loop
        CameraCoreModel.process_running = False

        # Wait for the thread to finish
        command_thread.join()

        # Check if the read_pipe function was never called
        mock_read_pipe.assert_not_called()

        # Check if the command queue is still empty
        self.assertEqual(CameraCoreModel.command_queue, [])

    @patch("threading.Thread.start")
    def test_start_preview_md_threads_all_threads_alive(self, mock_start):
        # Create mock threads that are all alive
        threads = [MagicMock(is_alive=MagicMock(return_value=True)) for _ in range(3)]

        # Call the function
        start_preview_md_threads(threads)

        # Check that start was not called on any thread
        mock_start.assert_not_called()

    @patch("threading.Thread.start")
    def test_start_preview_md_threads_some_threads_not_alive(self, mock_start):
        # Create mock threads, some of which are not alive
        threads = [
            MagicMock(is_alive=MagicMock(return_value=True)),
            MagicMock(is_alive=MagicMock(return_value=False)),
            MagicMock(is_alive=MagicMock(return_value=True)),
        ]

        # Call the function
        start_preview_md_threads(threads)

        # Check that start was called only on the thread that is not alive
        threads[1].start.assert_called_once()
        threads[0].start.assert_not_called()
        threads[2].start.assert_not_called()

    @patch("threading.Thread.start")
    def test_start_preview_md_threads_no_threads(self, mock_start):
        # Create an empty list of threads
        threads = []

        # Call the function
        start_preview_md_threads(threads)

        # Check that start was not called
        mock_start.assert_not_called()

    @patch("core.process.pause_preview_md_threads")
    def test_stop_all_cameras(self, mock_pause_preview_md_threads):
        # Mock the CameraCoreModel and its attributes
        cams = {
            "cam1": MagicMock(),
            "cam2": MagicMock(),
        }
        threads = [MagicMock(), MagicMock()]

        # Call the function
        stop_all_cameras(cams, threads)

        # Check if pause_preview_md_threads was called
        mock_pause_preview_md_threads.assert_called_once_with(cams, threads)

        # Check if stop_all was called for each camera
        for cam in cams.values():
            cam.stop_all.assert_called_once()

    @patch("core.process.pause_preview_md_threads")
    @patch("builtins.print")
    def test_stop_all_cameras_print(self, mock_print, mock_pause_preview_md_threads):
        # Mock the CameraCoreModel and its attributes
        cams = {
            "cam1": MagicMock(),
            "cam2": MagicMock(),
        }
        threads = [MagicMock(), MagicMock()]

        # Call the function
        stop_all_cameras(cams, threads)

        # Check if the correct message was printed
        mock_print.assert_called_once_with(
            "Stopping all cameras, encoders and preview/motion threads..."
        )

    @patch("core.process.execute_command")
    @patch("core.process.update_status_file")
    def test_execute_all_commands_invalid_group_command(
        self, mock_update_status_file, mock_execute_command
    ):
        # Mock the CameraCoreModel and its attributes
        CameraCoreModel.main_camera = "main_cam"
        cams = {"main_cam": MagicMock()}
        threads = []

        # Call the function with an invalid group command
        cmd_tuple = (["cmd1"], ["param1", "param2"])  # Mismatched lengths
        execute_all_commands(cams, threads, cmd_tuple)

        # Check if execute_command was called
        mock_execute_command.assert_called_once()

    @patch("core.process.execute_command")
    @patch("core.process.update_status_file")
    def test_execute_all_commands_invalid_single_command(
        self, mock_update_status_file, mock_execute_command
    ):
        # Mock the CameraCoreModel and its attributes
        CameraCoreModel.main_camera = "main_cam"
        cams = {"main_cam": MagicMock()}
        threads = []

        # Call the function with an invalid single command
        cmd_tuple = ("invalid_cmd", "param1")
        execute_all_commands(cams, threads, cmd_tuple)

        # Check if execute_command was called
        mock_execute_command.assert_called_once()

    @patch("core.process.execute_command")
    @patch("core.process.update_status_file")
    def test_execute_all_commands_group_command(
        self, mock_update_status_file, mock_execute_command
    ):
        # Mock the CameraCoreModel and its attributes
        CameraCoreModel.main_camera = "main_cam"
        cams = {"main_cam": MagicMock()}
        threads = []

        # Call the function with a group command
        cmd_tuple = (["cmd1", "cmd2"], ["param1", "param2"])
        execute_all_commands(cams, threads, cmd_tuple)

        # Check if execute_command was called for each command
        self.assertEqual(mock_execute_command.call_count, 2)

    @patch("core.process.execute_command")
    @patch("core.process.update_status_file")
    def test_execute_all_commands_single_command(
        self, mock_update_status_file, mock_execute_command
    ):
        # Mock the CameraCoreModel and its attributes
        CameraCoreModel.main_camera = "main_cam"
        cams = {"main_cam": MagicMock()}
        threads = []

        # Call the function with a single command
        cmd_tuple = ("cmd1", "param1")
        execute_all_commands(cams, threads, cmd_tuple)

        # Check if execute_command was called once
        mock_execute_command.assert_called_once_with(
            "main_cam", cams, threads, cmd_tuple
        )

    ############################################################################################################
    ############################################################################################################
    ############################################################################################################
    ############################################################################################################
    ############################################################################################################
    ############################################################################################################

    # Execute Command Tests

    ############################################################################################################
    # adding more command tests to grew coverage
    @patch("core.process.set_previews")
    def test_execute_command_balnk_cmd_code(self, mock_set_previews):
        cams = {0: MagicMock()}
        threads = []
        cmd_tuple = ("", "")

        execute_command(0, cams, threads, cmd_tuple)
        # return directly withou reaching the last call
        self.assertEqual(cams[0].print_to_logfile.call_count, 0)

    @patch("builtins.print")
    @patch("core.process.toggle_cam_record")
    def test_execute_command_start_video_with_duration(
        self, mock_toggle_cam_record, mock_print
    ):
        cams = {0: MagicMock()}
        cams[0].current_status = "active"
        cams[0].cam_index_str = "0"
        threads = []
        cmd_tuple = ("ca", "1 10")

        mock_toggle_cam_record.return_value = True

        execute_command(0, cams, threads, cmd_tuple)

        expected_calls = [
            call("Starting camera 0 video recording..."),
            call("Camera 0 record duration: 10"),
        ]
        mock_print.assert_has_calls(expected_calls)
        mock_toggle_cam_record.assert_called_once_with(cams[0], True)
        self.assertAlmostEqual(cams[0].record_until, time.monotonic() + 10, delta=1)

    @patch("builtins.print")
    def test_execute_command_stop_motion_detection(self, mock_print):
        cams = {0: MagicMock()}
        cams[0].current_status = "active"
        cams[0].cam_index_str = "0"
        threads = []
        cmd_tuple = ("md", "0")

        execute_command(0, cams, threads, cmd_tuple)

        expected_print_calls = [call("Stopping camera 0 motion detection...")]
        mock_print.assert_has_calls(expected_print_calls)
        self.assertEqual(cams[0].print_to_logfile.call_count, 2)
        self.assertFalse(cams[0].motion_detection)

    @patch("builtins.print")
    def test_execute_command_start_motion_detection(self, mock_print):
        cams = {0: MagicMock()}
        cams[0].current_status = "active"
        cams[0].cam_index_str = "0"
        threads = []
        cmd_tuple = ("md", "1")

        execute_command(0, cams, threads, cmd_tuple)

        expected_print_calls = [call("Starting camera 0 motion detection...")]
        mock_print.assert_has_calls(expected_print_calls)
        self.assertEqual(cams[0].print_to_logfile.call_count, 2)
        self.assertTrue(cams[0].motion_detection)

    def test_execute_command_switch_to_internal_mode(self):
        cams = {0: MagicMock()}
        cams[0].current_status = "active"
        cams[0].cam_index_str = "0"
        cams[0].config = {}
        threads = []
        cmd_tuple = ("mx", "0")

        execute_command(0, cams, threads, cmd_tuple)

        self.assertEqual(cams[0].config["motion_mode"], "internal")

    def test_execute_command_switch_to_monitor_mode(self):
        cams = {0: MagicMock()}
        cams[0].current_status = "active"
        cams[0].cam_index_str = "0"
        cams[0].config = {}
        threads = []
        cmd_tuple = ("mx", "2")

        execute_command(0, cams, threads, cmd_tuple)

        self.assertEqual(cams[0].config["motion_mode"], "monitor")

    @patch("builtins.print")
    def test_execute_command_set_motion_threshold(self, mock_print):
        cams = {0: MagicMock()}
        cams[0].current_status = "active"
        cams[0].cam_index_str = "0"
        threads = []
        cmd_tuple = ("mt", "50")

        execute_command(0, cams, threads, cmd_tuple)

        mock_print.assert_called_once_with("Setting motion parameters for camera 0")
        cams[0].set_motion_params.assert_called_once_with("mt", "50")

    @patch("builtins.print")
    def test_execute_command_set_valid_bitrate(self, mock_print):
        cams = {0: MagicMock()}
        cams[0].current_status = "active"
        cams[0].cam_index_str = "0"
        cams[0].config = {
            "video_bitrate": 1000000,
            "user_config": "uconfig",
        }
        threads = []
        cmd_tuple = ("bi", "5000000")

        execute_command(0, cams, threads, cmd_tuple)

        expected_print_calls = [call("Setting video bitrate for camera 0")]
        mock_print.assert_has_calls(expected_print_calls)
        self.assertEqual(cams[0].config["video_bitrate"], 5000000)

    @patch("builtins.print")
    def test_execute_command_set_invalid_bitrate_non_integer(self, mock_print):
        cams = {0: MagicMock()}
        cams[0].current_status = "active"
        cams[0].cam_index_str = "0"
        cams[0].config = {"video_bitrate": 1000000}
        threads = []
        cmd_tuple = ("bi", "invalid")

        execute_command(0, cams, threads, cmd_tuple)

        expected_print_calls = [
            call("Setting video bitrate for camera 0"),
            call("ERROR: Value is not an integer"),
        ]
        mock_print.assert_has_calls(expected_print_calls)
        self.assertEqual(cams[0].config["video_bitrate"], 1000000)

    @patch("builtins.print")
    def test_execute_command_set_bitrate_below_range(self, mock_print):
        cams = {0: MagicMock()}
        cams[0].current_status = "active"
        cams[0].cam_index_str = "0"
        cams[0].config = {"video_bitrate": 1000000}
        threads = []
        cmd_tuple = ("bi", "-1000")

        execute_command(0, cams, threads, cmd_tuple)

        expected_print_calls = [
            call("Setting video bitrate for camera 0"),
            call("ERROR: Bitrate must be between 0 and 25000000"),
        ]
        mock_print.assert_has_calls(expected_print_calls)
        self.assertEqual(cams[0].config["video_bitrate"], 1000000)

    @patch("builtins.print")
    def test_execute_command_set_bitrate_above_range(self, mock_print):
        cams = {0: MagicMock()}
        cams[0].current_status = "active"
        cams[0].cam_index_str = "0"
        cams[0].config = {"video_bitrate": 1000000}
        threads = []
        cmd_tuple = ("bi", "30000000")

        execute_command(0, cams, threads, cmd_tuple)

        expected_print_calls = [
            call("Setting video bitrate for camera 0"),
            call("ERROR: Bitrate must be between 0 and 25000000"),
        ]
        mock_print.assert_has_calls(expected_print_calls)
        self.assertEqual(cams[0].config["video_bitrate"], 1000000)

    @patch("builtins.print")
    def test_execute_command_set_annotation(self, mock_print):
        cams = {0: MagicMock()}
        cams[0].current_status = "active"
        cams[0].cam_index_str = "0"
        cams[0].config = {
            "user_config": "uconfig",
        }
        threads = []
        cmd_tuple = ("an", "Test Annotation")

        execute_command(0, cams, threads, cmd_tuple)

        self.assertEqual(cams[0].config["annotation"], "Test Annotation")

    def test_execute_command_set_file_count(self):
        cams = {0: MagicMock()}
        cams[0].current_status = "active"
        cams[0].cam_index_str = "0"
        threads = []
        cmd_tuple = ("sc", "")

        execute_command(0, cams, threads, cmd_tuple)

        cams[0].make_filecounts.assert_called_once_with()

    @patch("builtins.print")
    def test_execute_command_change_main_camera_invalid_slot(self, mock_print):
        cams = {0: MagicMock()}
        cams[0].current_status = "active"
        cams[0].cam_index_str = "0"
        threads = []
        cmd_tuple = ("cn", "1")

        execute_command(0, cams, threads, cmd_tuple)

        expected_print_calls = [
            call("Switching main camera slot"),
            call("ERROR: No camera detected in slot 1"),
        ]
        mock_print.assert_has_calls(expected_print_calls)

    @patch("builtins.print")
    def test_execute_command_change_main_camera_invalid_param(self, mock_print):
        cams = {0: MagicMock()}
        cams[0].current_status = "active"
        cams[0].cam_index_str = "0"
        threads = []
        cmd_tuple = ("cn", "invalid")

        execute_command(0, cams, threads, cmd_tuple)

        expected_print_calls = [
            call("Switching main camera slot"),
            call("ERROR: invalid is not a valid camera slot"),
        ]
        mock_print.assert_has_calls(expected_print_calls)

    @patch("core.process.capture_still_image")
    # @patch("core.process.CameraCoreModel.set_camera_configuration")
    # @patch("core.process.CameraCoreModel.restart")
    # @patch("core.model.CameraCoreModel.stop_all")
    @patch("core.process.pause_preview_md_threads")
    @patch("core.process.start_preview_md_threads")
    def test_execute_command_ix(
        self, mock_start_threads, mock_pause_threads, mock_capture_still_image
    ):
        cams = {0: MagicMock()}
        cams[0].current_status = "active"
        cams[0].cam_index_str = "0"
        cams[0].config = {
            "image_width": 1920,
            "image_height": 1080,
            "picam_buffer_count": 3,
        }
        cams[0].picam2 = MagicMock()
        cams[0].picam2.sensor_resolution = (3280, 2464)
        threads = []
        cmd_tuple = ("ix", "")

        execute_command(0, cams, threads, cmd_tuple)

        mock_pause_threads.assert_called_once_with(cams, threads)
        cams[0].stop_all.assert_called_once_with()
        cams[0].set_camera_configuration.assert_any_call("ix", ((3280, 2464, 1), 0))
        cams[0].restart.assert_any_call(False)
        mock_capture_still_image.assert_called_once_with(cams[0])
        cams[0].picam2.stop.assert_called_once_with()
        cams[0].set_camera_configuration.assert_any_call("ix", ((1920, 1080, 3), 1))
        cams[0].restart.assert_any_call(False)
        mock_start_threads.assert_called_once_with(threads)

    @patch("core.process.capture_stitched_image")
    # @patch("core.process.CameraCoreModel.set_camera_configuration")
    # @patch("core.process.CameraCoreModel.restart")
    # @patch("core.process.CameraCoreModel.stop_all")
    @patch("core.process.pause_preview_md_threads")
    @patch("core.process.start_preview_md_threads")
    def test_execute_command_ix_ix(
        self, mock_start_threads, mock_pause_threads, mock_capture_still_image
    ):
        cams = {0: MagicMock(), 1: MagicMock()}
        for i in cams:
            cams[i].current_status = "active"
            cams[i].cam_index_str = str(i)
            cams[i].config = {
                "image_width": 1920,
                "image_height": 1080,
                "picam_buffer_count": 3,
            }
            cams[i].picam2 = MagicMock()
            cams[i].picam2.sensor_resolution = (3280, 2464)
        threads = []
        cmd_tuple = ("ix+ix", "v")

        execute_command(0, cams, threads, cmd_tuple)

        mock_pause_threads.assert_called_once_with(cams, threads)

        self.assertEqual(cams[0].stop_all.call_count, 2)
        for i in cams:
            cams[i].set_camera_configuration.assert_any_call("ix", ((3280, 2464, 1), 0))
            cams[i].restart.assert_any_call(False)

        for i in cams:
            cams[i].picam2.stop.assert_called_once_with()
            cams[i].set_camera_configuration.assert_any_call("ix", ((1920, 1080, 3), 1))
            cams[i].restart.assert_any_call(False)
        mock_start_threads.assert_called_once_with(threads)

    ############################################################################################################

    @patch("builtins.print")
    def test_execute_command_sharpness(self, mock_print):
        cams = {0: MagicMock()}
        cams[0].current_status = "active"
        cams[0].cam_index_str = "0"
        threads = []
        cmd_tuple = ("sh", "32")
        execute_command(0, cams, threads, cmd_tuple)
        cams[0].set_image_adjustment.assert_called_once_with("Sharpness", 32.0)

    @patch("builtins.print")
    def test_execute_command_contrast(self, mock_print):
        cams = {0: MagicMock()}
        cams[0].current_status = "active"
        cams[0].cam_index_str = "0"
        threads = []
        cmd_tuple = ("co", "8")
        execute_command(0, cams, threads, cmd_tuple)
        cams[0].set_image_adjustment.assert_called_once_with("Contrast", 8.0)

    @patch("builtins.print")
    def test_execute_command_brightness(self, mock_print):
        cams = {0: MagicMock()}
        cams[0].current_status = "active"
        cams[0].cam_index_str = "0"
        threads = []
        cmd_tuple = ("br", "10")
        execute_command(0, cams, threads, cmd_tuple)
        cams[0].set_image_adjustment.assert_called_once_with("Brightness", 10.0)

    @patch("builtins.print")
    def test_execute_command_saturation(self, mock_print):
        cams = {0: MagicMock()}
        cams[0].current_status = "active"
        cams[0].cam_index_str = "0"
        threads = []
        cmd_tuple = ("sa", "18")
        execute_command(0, cams, threads, cmd_tuple)
        cams[0].set_image_adjustment.assert_called_once_with("Saturation", 18.0)

    @patch("builtins.print")
    def test_execute_command_awbmode(self, mock_print):
        cams = {0: MagicMock()}
        cams[0].current_status = "active"
        cams[0].cam_index_str = "0"
        threads = []
        cmd_tuple = ("wb", "auto")
        execute_command(0, cams, threads, cmd_tuple)
        cams[0].set_image_adjustment.assert_called_once_with("AwbMode", "auto")

    @patch("builtins.print")
    def test_execute_command_white_balance(self, mock_print):
        cams = {0: MagicMock()}
        cams[0].current_status = "active"
        cams[0].cam_index_str = "0"
        threads = []
        cmd_tuple = ("ag", "150 150")
        execute_command(0, cams, threads, cmd_tuple)
        cams[0].set_image_adjustment.assert_called_once_with("ColourGains", "150 150")

    @patch("builtins.print")
    def test_execute_command_shutterspeed(self, mock_print):
        cams = {0: MagicMock()}
        cams[0].current_status = "active"
        cams[0].cam_index_str = "0"
        threads = []
        cmd_tuple = ("ss", "20000")
        execute_command(0, cams, threads, cmd_tuple)
        cams[0].set_image_adjustment.assert_called_once_with("ExposureTime", 20000)

    @patch("builtins.print")
    def test_execute_command_exposure_compensation(self, mock_print):
        cams = {0: MagicMock()}
        cams[0].current_status = "active"
        cams[0].cam_index_str = "0"
        threads = []
        cmd_tuple = ("ec", "1")
        execute_command(0, cams, threads, cmd_tuple)
        cams[0].set_image_adjustment.assert_called_once_with("ExposureValue", 1)

    @patch("builtins.print")
    def test_execute_command_iso(self, mock_print):
        cams = {0: MagicMock()}
        cams[0].current_status = "active"
        cams[0].cam_index_str = "0"
        cams[0].config = {
            "analogue_gain": 8.0,
            "user_config": "uconfig",
        }
        threads = []
        cmd_tuple = ("is", "400")
        execute_command(0, cams, threads, cmd_tuple)
        cams[0].set_image_adjustment.assert_called_once_with("AnalogueGain", 400)

    @patch("builtins.print")
    def test_execute_command_quality(self, mock_print):
        cams = {0: MagicMock()}
        cams[0].current_status = "active"
        cams[0].cam_index_str = "0"
        cams[0].config = {
            "image_quality": 10,
            "user_config": "uconfig",
        }
        threads = []
        cmd_tuple = ("qu", "50")
        execute_command(0, cams, threads, cmd_tuple)
        self.assertEqual(cams[0].config["image_quality"], 50)

    @patch("builtins.print")
    def test_execute_command_pv(self, mock_print):
        cams = {0: MagicMock()}
        cams[0].current_status = "active"
        cams[0].cam_index_str = "0"
        cams[0].config = {
            "user_config": "uconfig",
        }
        threads = []
        cmd_tuple = ("pv", "20 128 2 128")
        execute_command(0, cams, threads, cmd_tuple)
        self.assertEqual(cams[0].config["preview_quality"], 20)
        self.assertEqual(cams[0].config["divider"], 2)
        self.assertEqual(cams[0].config["preview_size"], (128, 128))

    ############################################################################################################

    @patch("core.process.stop_all_cameras")
    @patch("core.process.start_preview_md_threads")
    def test_execute_command_run_stop_all(
        self, mock_start_preview_md_threads, mock_stop_all_cameras
    ):
        cams = {0: MagicMock()}
        threads = []
        cmd_tuple = ("ru", "0")

        execute_command(0, cams, threads, cmd_tuple)

        mock_stop_all_cameras.assert_called_once_with(cams, threads)

    @patch("core.process.stop_all_cameras")
    @patch("core.process.start_preview_md_threads")
    def test_execute_command_run_restart_all(
        self, mock_start_preview_md_threads, mock_stop_all_cameras
    ):
        cams = {0: MagicMock()}
        threads = []
        cmd_tuple = ("ru", "1")

        execute_command(0, cams, threads, cmd_tuple)

        mock_start_preview_md_threads.assert_called_once_with(threads)

    @patch("core.process.capture_still_image")
    def test_execute_command_image_capture(self, mock_capture_still_image):
        cams = {0: MagicMock()}
        threads = []
        cmd_tuple = ("im", "")

        execute_command(0, cams, threads, cmd_tuple)

        mock_capture_still_image.assert_called_once_with(cams[0])

    @patch("core.process.capture_stitched_image")
    def test_execute_command_stitched_image_capture(self, mock_capture_stitched_image):
        cams = {0: MagicMock()}
        threads = []
        cmd_tuple = ("im+im", "v")

        execute_command(0, cams, threads, cmd_tuple)

        mock_capture_stitched_image.assert_called_once_with(0, cams, 0)

    @patch("core.process.set_previews")
    def test_execute_command_display_preview(self, mock_set_previews):
        cams = {0: MagicMock()}
        threads = []
        cmd_tuple = ("dp", "1")

        execute_command(0, cams, threads, cmd_tuple)

        mock_set_previews.assert_called_once_with(cams)

    @patch("core.process.set_previews")
    def test_execute_command_display_preview_0(self, mock_set_previews):
        cams = {0: MagicMock()}
        threads = []
        cmd_tuple = ("dp", "0")

        execute_command(0, cams, threads, cmd_tuple)

        mock_set_previews.assert_called_once_with(cams)

    @patch("core.process.toggle_cam_record")
    def test_execute_command_start_video_recording(self, mock_toggle_cam_record):
        cams = {0: MagicMock()}
        threads = []
        cmd_tuple = ("ca", "1")

        execute_command(0, cams, threads, cmd_tuple)

        mock_toggle_cam_record.assert_called_once_with(cams[0], True)

    @patch("core.process.toggle_cam_record")
    def test_execute_command_stop_video_recording(self, mock_toggle_cam_record):
        cams = {0: MagicMock()}
        threads = []
        cmd_tuple = ("ca", "0")

        execute_command(0, cams, threads, cmd_tuple)

        mock_toggle_cam_record.assert_called_once_with(cams[0], False)

    @patch("core.process.pause_preview_md_threads")
    @patch("core.process.start_preview_md_threads")
    def test_execute_command_change_main_camera(
        self, mock_start_preview_md_threads, mock_pause_preview_md_threads
    ):
        cams = {0: MagicMock(), 1: MagicMock()}
        threads = []
        cmd_tuple = ("cn", "1")

        execute_command(0, cams, threads, cmd_tuple)

        mock_pause_preview_md_threads.assert_called_once_with(cams, threads)
        mock_start_preview_md_threads.assert_called_once_with(threads)

    @patch("core.process.pause_preview_md_threads")
    @patch("core.process.start_preview_md_threads")
    def test_execute_command_full_restart(
        self, mock_start_preview_md_threads, mock_pause_preview_md_threads
    ):
        cams = {0: MagicMock()}
        threads = []
        cmd_tuple = ("rs", "")

        execute_command(0, cams, threads, cmd_tuple)

        mock_pause_preview_md_threads.assert_called_once_with(cams, threads)
        mock_start_preview_md_threads.assert_called_once_with(threads)

    @patch("core.process.pause_preview_md_threads")
    @patch("core.process.start_preview_md_threads")
    def test_execute_command_quick_restart(
        self, mock_start_preview_md_threads, mock_pause_preview_md_threads
    ):
        cams = {0: MagicMock()}
        threads = []
        cmd_tuple = ("fl", "")

        execute_command(0, cams, threads, cmd_tuple)

        mock_pause_preview_md_threads.assert_called_once_with(cams, threads)
        mock_start_preview_md_threads.assert_called_once_with(threads)

    @patch("builtins.print")
    def test_execute_command_invalid_command(self, mock_print):
        cams = {0: MagicMock()}
        threads = []
        cmd_tuple = ("invalid", "")

        execute_command(0, cams, threads, cmd_tuple)

        mock_print.assert_called_once_with("Invalid command execution attempt.")
        self.assertEqual(cams[0].print_to_logfile.call_count, 2)

    @patch("builtins.print")
    def test_execute_command_camera_not_found(self, mock_print):
        cams = {}
        threads = []
        cmd_tuple = ("ca", "")

        execute_command(0, cams, threads, cmd_tuple)

        mock_print.assert_called_once_with(
            "No camera at index 0, cannot execute command"
        )

    @patch("builtins.print")
    def test_execute_command_camera_halted(self, mock_print):
        cams = {0: MagicMock()}
        cams[0].current_status = "halted"
        cams[0].cam_index_str = "0"  # Set the cam_index_str attribute
        threads = []
        cmd_tuple = ("ca", "")

        execute_command(0, cams, threads, cmd_tuple)

        # Assert the expected call
        expected_message = "Camera 0 status is halted. Cannot execute command."
        mock_print.assert_called_once_with(expected_message)


if __name__ == "__main__":
    unittest.main()
