import os
import time
import re
import threading
from core.control import execute_macro_command, set_previews, show_preview
from core.initialisation import update_status_file, write_to_user_config
from utilities.capture import capture_still_image, capture_stitched_image
from utilities.motion import motion_detection_thread
from utilities.record import toggle_cam_record
from core.model import CameraCoreModel


def parse_incoming_commands():
    """
    Continuously checks for incoming commands from the FIFO pipe.
    Valid commands are added to the command queue.
    """
    while CameraCoreModel.process_running:
        incoming_cmd = None
        fifo_fd = (
            CameraCoreModel.fifo_fd
        )  # Access the file descriptor for the FIFO pipe
        if fifo_fd:
            # Read and validate incoming commands from the pipe
            incoming_cmd = read_pipe(fifo_fd)
        if incoming_cmd:
            print("INFO: Got a piped command: " + str(incoming_cmd))
            # Add the valid command to the command queue
            with CameraCoreModel.cmd_queue_lock:
                CameraCoreModel.command_queue.append(incoming_cmd)
        time.sleep(CameraCoreModel.fifo_interval)  # Wait before checking the pipe again


def make_cmd_lists(contents_str):
    """
    Helper method for 'read_pipe'.
    If the cmd_code is a group-command in the format [x, y] for multiple
    cameras, turn it into an actual list (and the params) as well and
    validates each command in the list.

    Returns:
        cmd_list: Tuple containing ([cmd_codes], [cmd_params]) as long as
            a valid closing ] is found and all codes are valid, otherwise False.
    """
    if "]" not in contents_str:
        return False
    raw_codes, raw_params = contents_str.split("]", 1)
    raw_codes = raw_codes[1:].split(",")
    cmd_codes = [cmd.strip() for cmd in raw_codes]
    # Validate commands
    for cmd in cmd_codes:
        if not cmd:
            # Blank string, used to skip a camera.
            continue
        if cmd not in CameraCoreModel.VALID_COMMANDS:
            print("Invalid command: " + cmd)
            return False

    # Process the params. If not contained in [], it will be applied to all commands.
    # Otherwise, split on closing commas, unless escaped, as in "/,"
    cmd_params = raw_params.strip()
    if cmd_params:
        if (cmd_params[0] == "[") and (cmd_params[-1] == "]"):
            # Has individual parameters for each cameras.
            parsed_params = re.split("""(?<!/)\\,""", cmd_params[1:-1])
            # Replace any escaped commas with plain commas.
            cmd_params = [param.replace("/,", ",") for param in parsed_params]
        else:
            # Make params list by duplicating as many times as there are commands.
            parsed_params = []
            for cmd in cmd_codes:
                parsed_params.append(cmd_params)
            cmd_params = parsed_params
    else:
        # No parameters.
        cmd_params = []

    # If more command codes exist than param sets, pad with blank commands for the remainder.
    while len(cmd_params) < len(cmd_codes):
        cmd_params.append("")
    return (cmd_codes, cmd_params)


def read_pipe(fd):
    """
    Reads data from the FIFO pipe and checks if it is a valid command.

    Args:
        fd: File descriptor of the FIFO pipe.

    Returns:
        Tuple of command and parameters if valid, otherwise False.
    """
    # Read the contents from the pipe and remove any trailing whitespace
    try:
        contents = os.read(fd, CameraCoreModel.MAX_COMMAND_LEN)
    except BlockingIOError as e:
        print("ERROR: read_pipe(): " + str(e))
        return False
    contents_str = contents.decode().rstrip()
    cmd_code = contents_str[:2]  # Extract the command code (first 2 characters)
    cmd_param = contents_str[
        3:
    ]  # Extract the command parameters (after first 2 characters)
    # Check if the command is valid based on predefined valid commands
    if len(contents_str) > 0:
        print("INFO: read_pipe(): '" + contents_str + "'")
        # Check for group command (multiple cameras)
        if cmd_code[0] == "[":
            print("Group command received: " + contents_str)
            cmd_group = make_cmd_lists(contents_str)
            return cmd_group
        else:
            # Single command.
            if cmd_code in CameraCoreModel.VALID_COMMANDS:
                print("Valid command received: " + cmd_code)
                print("Command parameters: " + cmd_param)
                return (cmd_code, cmd_param)  # Return the command code and parameters
            else:
                print("Invalid command: " + contents_str)
    return False  # Return False for invalid commands


def execute_all_commands(cams, threads, cmd_tuple):
    """
    Checks whether commands are a group command ([], []) for multiple cameras
    or a single command for the main camera and executes them accordingly.

    Args:
        cams: All available CameraCoreModels for each attached camera.
        threads: Preview and Motion Detect threads.
        cmd_tuple: Tuple containing command code(s) and parameters.
    """
    cmd_code, cmd_param = cmd_tuple  # Unpack the command tuple

    # Check if command is a group command
    if isinstance(cmd_code, list):
        # Group command. Execute on all cameras.
        print("Group command: ")
        print(cmd_code)
        print(cmd_param)
        for index, cmd in enumerate(cmd_code):
            cmds = (cmd_code[index], cmd_param[index])
            execute_command(index, cams, threads, cmds)
    else:
        # Single command. Execute on main camera.
        execute_command(CameraCoreModel.main_camera, cams, threads, cmd_tuple)
    # Update status files after command execution
    update_status_file(cams[CameraCoreModel.main_camera])


def execute_command(index, cams, threads, cmd_tuple):
    """
    Executes the given command based on its code.

    Args:
        index: Index number of the camera executing the command.
        cams: All available CameraCoreModels for attached cameras.
        threads: Preview and Motion Detect threads.
        cmd_tuple: Tuple containing command code(s) and parameters.
    """
    if index not in cams:
        print(f"No camera at index {index}, cannot execute command")
        return
    cmd_code, cmd_param = cmd_tuple
    if not cmd_code:
        return

    requires_full_restart = {"px", "rs", "cs", "cr", "1s", "ix", "ix+ix"}
    requires_quick_restart = {"fl"}
    model = cams[index]
    num = model.cam_index_str
    success = False
    CameraCoreModel.debug_execution_time = time.monotonic()

    match cmd_code:
        case "ru":  # Restart/stop all cameras
            if cmd_param.startswith("0"):
                stop_all_cameras(cams, threads)
            else:
                print("Restarting all cameras, encoders and preview/motion threads...")
                for cam in cams.values():
                    cam.restart(True)
                start_preview_md_threads(threads)
        case "im":  # Capture a still image
            capture_still_image(model)
        case "im+im":  # Capture stitched image from all cameras
            axis = 0 if cmd_param == "v" else 1
            capture_stitched_image(index, cams, axis)
        case "dp":  # Display preview toggle
            model.show_preview = cmd_param != "0"
            set_previews(cams)
            success = True
        case "ca":  # Camera action (start/stop video)
            if cmd_param.startswith("1"):
                print(f"Starting camera {num} video recording...")
                success = toggle_cam_record(model, True)
                if success and cmd_param[2:].isnumeric():
                    duration = int(cmd_param[2:])
                    if duration > 0:
                        model.record_until = time.monotonic() + duration
            else:
                print(f"Stopping camera {num} video recording...")
                model.record_until = None
                toggle_cam_record(model, False)
        case "md":  # Motion detection toggle
            model.motion_detection = cmd_param != "0"
            model.print_to_logfile(
                "Internal motion detection "
                + ("started" if model.motion_detection else "stopped")
            )
        case "mx":  # Change motion detection mode
            model.config["motion_mode"] = "internal" if cmd_param == "0" else "monitor"
        case "mt" | "ms" | "mb" | "me":  # Motion parameters adjustment
            print(f"Setting motion parameters for camera {num}")
            success = model.set_motion_params(cmd_code, cmd_param)
        case "bi":  # Set video bitrate
            print(f"Setting video bitrate for camera {num}")
            try:
                new_bitrate = int(cmd_param)
                if 0 <= new_bitrate <= 25000000:
                    model.config["video_bitrate"] = new_bitrate
                    success = True
                else:
                    print("ERROR: Bitrate must be between 0 and 25000000")
            except ValueError:
                print("ERROR: Value is not an integer")
        case "an":  # Set annotation text
            model.config["annotation"] = cmd_param
            success = True
        case "sc":  # Update image/video file count
            model.make_filecounts()
        case "cn":  # Change main camera slot
            try:
                new_main = int(cmd_param)
                if new_main in cams:
                    pause_preview_md_threads(cams, threads)
                    CameraCoreModel.main_camera = new_main
                    start_preview_md_threads(threads)
                else:
                    print(f"ERROR: No camera detected in slot {cmd_param}")
            except ValueError:
                print(f"ERROR: {cmd_param} is not a valid camera slot")
        case "sh" | "co" | "br" | "sa" | "wb" | "ag" | "ss" | "ec" | "is" | "qu":
            # Image adjustments: sharpness, contrast, brightness, saturation, etc.
            print(f"Setting {cmd_code} for camera {model.cam_index_str} to {cmd_param}")
            success = model.set_image_adjustment(cmd_code, cmd_param)
        case "pv":  # Adjust preview settings
            try:
                quality, width, divider, *height = map(int, cmd_param.split(" "))
                model.config.update(
                    preview_quality=max(1, min(100, quality)),
                    divider=divider,
                    preview_size=(
                        width,
                        height[0] if height else int((width / 16) * 9),
                    ),
                )
                success = True
            except ValueError:
                print("Invalid values for settings")
        case "sy":  # Execute macro command
            script_name, *args = cmd_param.split(" ")
            success = execute_macro_command(model, script_name, args)
            if success:
                print(f"Successfully executed macro: {script_name} with args: {args}")
        case "tl":  # Toggle timelapse
            model.timelapse_on = cmd_param == "1"
            model.make_filecounts()
            update_status_file(cams[CameraCoreModel.main_camera])
            model.print_to_logfile(
                "Timelapse " + ("started" if model.timelapse_on else "stopped")
            )
        case "tv":  # Set timelapse interval
            try:
                new_tl_interval = int(cmd_param)
                if 1 <= new_tl_interval <= (24 * 60 * 60 * 10):
                    model.config["tl_interval"] = new_tl_interval
                    success = True
                else:
                    print(
                        "ERROR: timelapse interval must be between 1 and (24*60*60*10)."
                    )
            except ValueError:
                print("ERROR: tv Value is not an integer")
        case cmd if cmd in requires_full_restart:
            # Commands needing full restart
            print(f"Altering camera {num} configuration")
            pause_preview_md_threads(cams, threads)
            success = model.set_camera_configuration(cmd_code, cmd_param)
            model.restart(False)
            start_preview_md_threads(threads)
        case cmd if cmd in requires_quick_restart:
            # Commands needing quick restart
            pause_preview_md_threads(cams, threads)
            model.picam2.stop()
            success = model.set_camera_configuration(cmd_code, cmd_param)
            model.restart(False)
            start_preview_md_threads(threads)
        case _:
            print("Invalid command execution attempt.")
            model.print_to_logfile("Unrecognised pipe command")

    CameraCoreModel.debug_execution_time = (
        time.monotonic() - CameraCoreModel.debug_execution_time
    )
    model.print_to_logfile(
        f"Attempted to execute '{cmd_code}' with parameters ({cmd_param}). "
        + f"Attempt took {CameraCoreModel.debug_execution_time} seconds."
    )
    if success:
        write_to_user_config(model, cmd_code, cmd_param)


def pause_preview_md_threads(cams, threads):
    """
    Terminates the preview and MD threads and makes a new set ready to
    restart afterwards.
    """
    # Temporarily set camera status to halted to allow threads to terminate.
    cams[CameraCoreModel.main_camera].current_status = "halted"
    # Stop preview and motion-detection threads
    for t in threads:
        if t.is_alive():
            t.join()
    cams[CameraCoreModel.main_camera].set_status()
    # Make new threads to replace them, but don't start them until restart is called.
    preview_thread = threading.Thread(target=show_preview, args=(cams,))
    md_thread = threading.Thread(target=motion_detection_thread, args=(cams,))
    threads.clear()
    threads.append(preview_thread)
    threads.append(md_thread)


def start_preview_md_threads(threads):
    """
    Starts the preview and MD threads.
    """
    for t in threads:
        if not t.is_alive():
            t.start()


def stop_all_cameras(cams, threads):
    """
    Terminates preview/MD threads and stops all cameras and any encoders
    they may be running and resets motion detection flags.
    """
    print("Stopping all cameras, encoders and preview/motion threads...")
    pause_preview_md_threads(cams, threads)
    for cam in cams.values():
        cam.stop_all()
