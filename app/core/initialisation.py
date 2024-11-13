import os
import signal
import threading
import time
from picamera2 import Picamera2
from core.model import CameraCoreModel
from core.command import execute_all_commands, parse_incoming_commands, start_preview_md_threads
from core.control import set_previews, show_preview
from utilities.record import toggle_cam_record
from utilities.capture import capture_still_image
from utilities.motion import motion_detection_thread, setup_motion_pipe


def on_sigint_sigterm(sig, frame):
    """
    Signal handler for SIGINT and SIGTERM.
    Sets process_running to False, allowing graceful shutdown.

    Args:
        sig: Signal number.
        frame: Current stack frame.
    """
    print("Received signal: ")
    print(sig)
    CameraCoreModel.process_running = False


# Register signal handlers for graceful shutdown
signal.signal(signal.SIGINT, on_sigint_sigterm)
signal.signal(signal.SIGTERM, on_sigint_sigterm)


def update_status_file(model):
    """
    Updates the status file with the current camera status.

    Args:
        model: CameraCoreModel instance containing the status and config.
    """
    model.set_status()
    current_status = model.current_status  # Get the current status from the model
    status_filepath = model.config["status_file"]  # Path to the status file
    status_dir = os.path.dirname(
        status_filepath
    )  # Get the directory of the status file

    # Create the status directory if it doesn't exist
    if not os.path.exists(status_dir):
        os.makedirs(status_dir)

    # Write the current status to the status file
    if current_status:
        status_file = open(status_filepath, "w")
        status_file.write(current_status)
        status_file.close()


def write_to_user_config(cam, cmd_code, cmd_param):
    """
    Write changes made to a camera's configuration into their associated user_config file.

    Args:
        cam: CameraCoreModel instance.
        cmd_code : Command to check against valid commands dict.
        cmd_param : Parameters received from input.
    """
    setting = CameraCoreModel.VALID_COMMANDS[cmd_code]
    params = cmd_param.split(" ")
    # Update the camera's write_to_config dict, if the setting is configurable.
    if setting:
        # Special cases for '1s', 'fl' and 'dp', need to turn 0/1 into "true/false" strings.
        if cmd_code == "dp":
            if cmd_param == "0":
                cam.write_to_config[setting] = "false"
            else:
                cam.write_to_config[setting] = "true"
        elif cmd_code == "fl":
            if cam.config["hflip"] == 1:
                cam.write_to_config["hflip"] = "true"
            else:
                cam.write_to_config["hflip"] = "false"
            if cam.config["vflip"] == 1:
                cam.write_to_config["vflip"] = "true"
            else:
                cam.write_to_config["vflip"] = "false"
        elif cmd_code == "1s":
            if cam.solo_stream_mode:
                cam.write_to_config["solo_stream_mode"] = "true"
            else:
                cam.write_to_config["solo_stream_mode"] = "false"
        elif isinstance(setting, list):
            # This command changes multiple settings, may have optional parameters.
            # Populate the listed settings for as many parameters as were given.
            for index, value in enumerate(setting):
                if index < len(params):
                    cam.write_to_config[value] = params[index]
            # Special case for 'pv's optional height parameter.
            if cmd_code == "pv":
                cam.write_to_config["height"] = str(cam.config["preview_size"][1])
        else:
            cam.write_to_config[setting] = cmd_param

        # Write the camera's write_to_config dict to file.
        with open(cam.config["user_config"], "w") as uconfig:
            for key, value in cam.write_to_config.items():
                line = key + " " + value + "\n"
                uconfig.write(line)


def setup_fifo(path):
    """
    Sets up the FIFO named pipe for receiving commands.

    Args:
        path: String containing filepath of control file.
    Returns:
        True upon success, False upon failure.
    """
    # Get/make directory for the FIFO control pipe
    fifo_dir = os.path.dirname(path)
    if not os.path.exists(fifo_dir):
        os.makedirs(fifo_dir)
    # If the control file (FIFO) doesn't exist, create it
    if not os.path.exists(path):
        print("ALERT: Control file does not exist. Making new FIFO control file.")
        os.mkfifo(path, 0o6666)
    # Open the FIFO file in non-blocking read mode and flush any existing data
    CameraCoreModel.fifo_fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK, 0o666)
    try:
        os.read(CameraCoreModel.fifo_fd, CameraCoreModel.MAX_COMMAND_LEN)  # Flush pipe
    except BlockingIOError as e:
        print("ERROR: setup_fifo(): FIFO pipe busy, cannot flush - " + str(e))
        """
        commented to allow the program to load despite a pipe error:
        os.close(CameraCoreModel.fifo_fd)  # Close the FIFO pipe
        return False
        """
    return True


def start_background_process(config_filepath):
    """
    Main background process that sets up the camera and handles the command loop.

    Args:
        config_filepath: Path to the configuration file.
    """
    print(f"Starting {CameraCoreModel.APP_NAME} main process...")
    all_cameras = (
        Picamera2.global_camera_info()
    )  # Get information about attached cameras
    print(all_cameras)
    # Check if any cameras are attached
    if not all_cameras:
        print("No attached cameras detected. Exiting program.")
        return

    # Set up the cameras
    cams = {}
    for index, c in enumerate(all_cameras):
        if "Num" not in c:
            c["Num"] = index
        if CameraCoreModel.main_camera is None:
            CameraCoreModel.main_camera = c["Num"]
        config_file = None
        if config_filepath:
            if index < len(config_filepath):
                config_file = config_filepath[index]
        cams[c["Num"]] = CameraCoreModel(c, config_file)
        cams[c["Num"]].print_to_logfile(
            "Created Picamera2 instance for camera in slot " + str(c["Num"])
        )
    # Set up camera previews.
    set_previews(cams)

    # Setup FIFO for receiving commands
    if not setup_fifo(cams[CameraCoreModel.main_camera].config["control_file"]):
        cams[CameraCoreModel.main_camera].teardown()
        return

    # Setup motion pipe file
    setup_motion_pipe(cams[CameraCoreModel.main_camera].config["motion_pipe"])

    # Set the process to running
    CameraCoreModel.process_running = True

    # Write status to the status file.
    update_status_file(cams[CameraCoreModel.main_camera])

    # Start a thread to continuously parse incoming commands
    cmd_processing_thread = threading.Thread(target=parse_incoming_commands)
    cmd_processing_thread.start()

    # Create threads for preview and motion detection.
    preview_thread = threading.Thread(target=show_preview, args=(cams,))
    md_thread = threading.Thread(target=motion_detection_thread, args=(cams,))

    threads = [preview_thread, md_thread]

    # Start threads if camera is ready (autostart is not off)
    if cams[CameraCoreModel.main_camera].current_status != "halted":
        start_preview_md_threads(threads)

    # Initialize the timelapse timer that periodically triggers the image capture.
    # Note: This assumes each command loop runs for .01 seconds, which is really the minimum time it will run.
    # It would be better to implement an algorithm here that reads the realtime clock to detect when
    # the tl_interval has elapsed to trigger the image capture.
    tl_interval_loops = cams[CameraCoreModel.main_camera].config["tl_interval"] * 10
    timelapse_timer = tl_interval_loops

    # Execute commands off the queue as they come in.
    while CameraCoreModel.process_running:
        # Check if mutex lock can be acquired (i.e. FIFO thread is not writing to the command queue)
        # before popping from the command queue and attempting to execute. If lock can't be acquiring,
        # skip and check on the next loop cycle instead of blocking.
        # Without being non-blocking, anyone spamming the FIFO with commands will freeze/delay this thread.
        cmd_queue = CameraCoreModel.command_queue
        cmd_queue_lock = CameraCoreModel.cmd_queue_lock
        if (
            (cmd_queue)
            and (cmd_queue_lock.acquire(blocking=False))
            and (cams[CameraCoreModel.main_camera].current_status)
        ):
            next_cmd = CameraCoreModel.command_queue.pop(0)  # Get the next command
            cmd_queue_lock.release()
            execute_all_commands(cams, threads, next_cmd)
        # Check for recording duration and stop recording if duration has elapsed.
        for cam_index in cams:
            cam = cams[cam_index]
            if cam.record_until:
                if cam.record_until <= time.monotonic():
                    toggle_cam_record(cam, False)
                    cam.record_until = None
                    print("Video recording duration complete.")
        # Capture timelapse images
        if cams[CameraCoreModel.main_camera].timelapse_on:
            timelapse_timer += 1
            if timelapse_timer > tl_interval_loops:
                capture_still_image(cams[CameraCoreModel.main_camera])
                timelapse_timer = 0
        time.sleep(0.01)  # Small delay before next iteration

    print("Shutting down gracefully...")
    for cam_index in cams:
        cams[cam_index].current_status = "halted"
    cmd_processing_thread.join()  # Wait for command processing thread to finish
    for t in threads:
        # Terminate preview and motion-detection threads.
        if t.is_alive():
            t.join()
    for cam_index in cams:
        cam = cams[cam_index]
        cam.teardown()  # Teardown the camera and stop it
        update_status_file(cam)  # Update the status file with halted status
    os.close(CameraCoreModel.fifo_fd)  # Close the FIFO pipe
