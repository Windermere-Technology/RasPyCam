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
    # Check whether camera exists at index, if not don't bother with anything.
    if index not in cams:
        print(f"No camera at index {index}, cannot execute command")
        return
    cmd_code, cmd_param = cmd_tuple  # Unpack the command tuple
    # Do nothing if command is blank.
    if not cmd_code:
        return
    requires_full_restart = ["px", "rs", "cs", "cr", "1s", "ix", "ix+ix"]
    # Picture settings, ReSet config, Change Size, Change Resolution, Single-Stream mode, Image-capture maX-resolution
    requires_quick_restart = ["fl"]  # FLip

    model = cams[index]
    num = model.cam_index_str
    success = False
    CameraCoreModel.debug_execution_time = time.monotonic()
    if cmd_code == "ru":  # 'ru' stands for "run"
        if cmd_param.startswith("0"):
            stop_all_cameras(cams, threads)
        else:
            print("Restarting all cameras, encoders and preview/motion threads...")
            for cam in cams.values():
                cam.restart(True)  # Reloads config values from user_config file.
            start_preview_md_threads(threads)
    elif model.current_status != "halted":
        if cmd_code == "im":  # 'im' stands for "image capture"
            capture_still_image(model)
        elif (
            cmd_code == "im+im"
        ):  # NEW COMMAND - Captures stitched image from all cameras.
            axis = 0 if cmd_param == "v" else 1
            capture_stitched_image(index, cams, axis)
        elif (
            cmd_code == "dp"
        ):  # NEW COMMAND - Display Preview. Turns on/off preview for a camera.
            # Stitches previews, if more than one camera has it turned on.
            if cmd_param == "0":
                model.show_preview = False
            else:
                model.show_preview = True
            set_previews(cams)
            success = True
        elif cmd_code == "ca":  # 'ca' stands for "camera action" (start/stop video)
            if cmd_param.startswith("1"):
                print(f"Starting camera {num} video recording...")
                success = toggle_cam_record(model, True)
                if success:
                    # Only apply duration if started recording.
                    duration = cmd_param[2:]
                    if duration.isnumeric():
                        print(f"Camera {num} record duration: {duration}")
                        duration = int(duration)
                        if duration > 0:
                            model.record_until = time.monotonic() + duration
            else:
                print(f"Stopping camera {num} video recording...")
                model.record_until = None
                toggle_cam_record(model, False)
        elif cmd_code == "md":  # 'md' stands for "motion detection"
            if (cmd_param == "0") or not cmd_param:
                print(f"Stopping camera {num} motion detection...")
                model.motion_detection = False
                model.print_to_logfile("Internal motion detection stopped")
            else:
                print(f"Starting camera {num} motion detection...")
                model.motion_detection = True
                model.print_to_logfile("Internal motion detection started")
        elif (
            cmd_code == "mx"
        ):  # Switches detection mode. No implementation for Mode 1 yet.
            if cmd_param == "0":
                # Internal mode.
                model.config["motion_mode"] = "internal"
            elif cmd_param == "2":
                # Monitor mode.
                model.config["motion_mode"] = "monitor"
        elif (
            (cmd_code == "mt")
            or (cmd_code == "ms")
            or (cmd_code == "mb")
            or (cmd_code == "me")
        ):
            # Changes motion detection parameters (threshold, initframs, startframes, stopframes)
            print(f"Setting motion parameters for camera {num}")
            success = model.set_motion_params(cmd_code, cmd_param)
        elif cmd_code == "bi":
            print(
                f"Setting video bitrate for camera {num}"
            )  # 'bi' stands for "bitrate"
            new_bitrate = model.config["video_bitrate"]
            try:
                new_bitrate = int(cmd_param)
                if (new_bitrate < 0) or (new_bitrate > 25000000):
                    print("ERROR: Bitrate must be between 0 and 25000000")
                else:
                    model.config["video_bitrate"] = new_bitrate
                    success = True
            except ValueError:
                print("ERROR: Value is not an integer")
        elif cmd_code == "an":  # Annotation text.
            model.config["annotation"] = cmd_param
            success = True
        elif cmd_code == "sc":  # Set Count of image/video files
            model.make_filecounts()
        elif cmd_code == "cn":  # Change Number of main camera.
            # Threads need to stop, but not the actual camera instances.
            print("Switching main camera slot")
            try:
                new_main = int(cmd_param)
                if new_main not in cams:
                    print(f"ERROR: No camera detected in slot {cmd_param}")
                else:
                    pause_preview_md_threads(cams, threads)
                    CameraCoreModel.main_camera = new_main
                    start_preview_md_threads(threads)
            except ValueError:
                print(f"ERROR: {cmd_param} is not a valid camera slot")
        elif cmd_code == "sh":  # Sharpness
            print(f"Setting sharpness for camera {model.cam_index_str} to {cmd_param}")
            try:
                success = model.set_image_adjustment("Sharpness", float(cmd_param))
            except ValueError:
                print("Invalid sharpness value")

        elif cmd_code == "co":  # Contrast
            print(f"Setting contrast for camera {model.cam_index_str} to {cmd_param}")
            try:
                success = model.set_image_adjustment("Contrast", float(cmd_param))
            except ValueError:
                print("Invalid contrast value")

        elif cmd_code == "br":  # Brightness
            print(f"Setting brightness for camera {model.cam_index_str} to {cmd_param}")
            try:
                success = model.set_image_adjustment("Brightness", float(cmd_param))
            except ValueError:
                print("Invalid brightness value")
        elif cmd_code == "sa":  # Saturation
            print(f"Setting saturation for camera {model.cam_index_str} to {cmd_param}")
            try:
                success = model.set_image_adjustment("Saturation", float(cmd_param))
            except ValueError:
                print("Invalid saturation value")
        elif cmd_code == "wb":  # White Balance
            print(
                f"Setting white balance for camera {model.cam_index_str} to {cmd_param}"
            )
            success = model.set_image_adjustment("AwbMode", cmd_param)
        elif cmd_code == "ag":  # Color Gains
            print(
                f"Setting colour gains for camera {model.cam_index_str} to {cmd_param}"
            )
            success = model.set_image_adjustment("ColourGains", cmd_param)
        elif cmd_code == "ss":  # Shutter Speed/Exposure Time
            print(
                f"Setting shutter speed for camera {model.cam_index_str} to {cmd_param}"
            )
            try:
                success = model.set_image_adjustment("ExposureTime", int(cmd_param))
            except ValueError:
                print("Invalid shutter speed value")
        elif cmd_code == "ec":  # Exposure Compensation value
            print(
                f"Setting exposure compensation for camera {model.cam_index_str} to {cmd_param}"
            )
            try:
                success = model.set_image_adjustment("ExposureValue", int(cmd_param))
            except ValueError:
                print("Invalid exposure compensation value")
        elif cmd_code == "is":  # ISO / AnalogueGain.
            print(f"Setting ISO for camera {model.cam_index_str} to {cmd_param}")
            try:
                success = model.set_image_adjustment("AnalogueGain", int(cmd_param))
            except ValueError:
                print("Invalid ISO value")
        elif (
            cmd_code == "qu"
        ):  # Still image QUality level. Should be between 1 and 100. Default 75.
            print(
                f"Setting still image quality for camera {model.cam_index_str} to {cmd_param}"
            )
            try:
                model.config["image_quality"] = max(1, min(100, int(cmd_param)))
                model.picam2.options["quality"] = model.config["image_quality"]
                success = True
            except ValueError:
                print("Invalid JPEG quality value")
        elif cmd_code == "pv":  # Adjust Preview settings.
            print(
                f"Adjusting preview settings for camera {model.cam_index_str} to {cmd_param}"
            )
            settings = cmd_param.split(" ")
            try:
                quality = settings[0]
                width = int(settings[1])
                divider = int(settings[2])
                if len(settings) > 3:
                    height = int(settings[3])
                else:
                    height = int((width / 16) * 9)
                model.config["preview_quality"] = max(1, min(100, int(quality)))
                model.config["divider"] = divider
                model.config["preview_size"] = (width, height)
                success = True
            except ValueError:
                print("Invalid values for settings")
        elif cmd_code == "sy":
            parts = cmd_param.split(" ")
            script_name = parts[0]
            args = parts[1:] if len(parts) > 1 else []
            success = execute_macro_command(model, script_name, args)
            if success:
                print(f"Successfully executed macro: {script_name} with args: {args}")
            return
        elif cmd_code == "tl":  # Start or stop the gathering of timelapse images.
            if int(cmd_param) == 1:
                model.timelapse_on = True
                model.make_filecounts()
                model.timelapse_count = 1
                update_status_file(cams[CameraCoreModel.main_camera])
                model.print_to_logfile("Timelapse started")
                print("Timelapse started")
            elif int(cmd_param) == 0:
                model.timelapse_on = False
                update_status_file(cams[CameraCoreModel.main_camera])
                model.print_to_logfile("Timelapse stopped")
                print("Timelapse stopped")
            else:
                model.print_to_logfile(f"ERROR: bad argument to tl: {cmd_param}")
                print(f"ERROR: Invalid 'tl' argument: {cmd_param}")
        elif cmd_code == "tv":  # set timelapse interval
            print("Setting timelapse interval")  # 'tv' stands for "timelapse interval"
            new_tl_interval = model.config["tl_interval"]
            try:
                new_tl_interval = int(cmd_param)
                if (new_tl_interval < 1) or (new_tl_interval > (24 * 60 * 60 * 10)):
                    print(
                        "ERROR: timelapse interval must be between 1 and (24*60*60*10)."
                    )
                else:
                    model.config["tl_interval"] = new_tl_interval
                    success = True
            except ValueError:
                print("ERROR: tv Value is not an integer")
        elif cmd_code in requires_full_restart:
            print(f"Altering camera {num} configuration")
            # These need the encoder to be fully stopped to work.
            pause_preview_md_threads(cams, threads)
            model.stop_all()
            if cmd_code == "ix":
                orig_dims = (
                    model.config["image_width"],
                    model.config["image_height"],
                    model.config["picam_buffer_count"],
                )
                max_w = model.picam2.sensor_resolution[0]
                max_h = model.picam2.sensor_resolution[1]
                model.set_camera_configuration("ix", ((max_w, max_h, 1), 0))
                model.restart(False)
                capture_still_image(model)
                model.picam2.stop()
                model.set_camera_configuration("ix", (orig_dims, 1))
                model.restart(False)
            elif cmd_code == "ix+ix":
                orig_dims = {}
                for i, cam in cams.items():
                    cam.stop_all()
                    orig_dims[i] = (
                        cam.config["image_width"],
                        cam.config["image_height"],
                        cam.config["picam_buffer_count"],
                    )
                    max_dims = (
                        model.picam2.sensor_resolution[0],
                        model.picam2.sensor_resolution[1],
                        1,
                    )
                    cam.set_camera_configuration("ix", (max_dims, 0))
                    cam.restart(False)
                axis = 0 if cmd_param == "v" else 1
                capture_stitched_image(index, cams, axis)
                for i, cam in cams.items():
                    cam.picam2.stop()
                    cam.set_camera_configuration("ix", (orig_dims[i], 1))
                    cam.restart(False)
            else:
                success = model.set_camera_configuration(cmd_code, cmd_param)
                model.restart(False)  # Do NOT reload settings from user_configs.
            set_previews(cams)
            start_preview_md_threads(threads)
        elif cmd_code in requires_quick_restart:
            # These don't need the encoder to be stopped, can theoretically keep recording video
            # throughout, but will result in frozen portions while this command executes.
            pause_preview_md_threads(cams, threads)
            model.picam2.stop()
            success = model.set_camera_configuration(cmd_code, cmd_param)
            model.restart(False)
            start_preview_md_threads(threads)
        else:
            print("Invalid command execution attempt.")
            model.print_to_logfile("Unrecognised pipe command")
    else:
        print(f"Camera {num} status is halted. Cannot execute command.")
    # Print Command Execution Info to Log
    CameraCoreModel.debug_execution_time = (
        time.monotonic() - CameraCoreModel.debug_execution_time
    )
    model.print_to_logfile(
        f"Attempted to execute '{cmd_code}' with parameters ({cmd_param}). "
        + f"Attempt took {CameraCoreModel.debug_execution_time} seconds."
    )
    # Write any configurable settings changes to the camera's user_config file if successful.
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
