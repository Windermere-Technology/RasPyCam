import os
import time
import subprocess
from core.model import CameraCoreModel
from utilities.preview import generate_preview


def set_previews(cams):
    """
    Updates CameraCoreModel's show_previews array based on whether cameras
    are flagged to show previews.
    """
    with CameraCoreModel.preview_dict_lock:
        for index, cam in cams.items():
            CameraCoreModel.show_previews[index] = cam.show_preview


def show_preview(cams):
    """
    Method used for preview thread. Continuously creates the preview image.
    Running in its own thread minimizes disruption from still capture and
    other command execution.

    Args:
        cam: Camera instance used to generate preview.
    """
    while cams[CameraCoreModel.main_camera].current_status != "halted":
        # Generate a preview for the current frame, according to FPS divider.
        main_cam = cams[CameraCoreModel.main_camera]
        frame_delay = int(main_cam.config["video_fps"] / main_cam.config["divider"])
        generate_preview(cams)
        time.sleep(1 / frame_delay)


def execute_macro_command(model, script_name, args):
    """
    Executes a macro script from the directory specified in the model's configuration.

    Args:
        model (CameraCoreModel): The camera model instance containing configuration details.
        script_name (str): The name of the macro script file (e.g., "somemacro.sh").
        args (list): List of arguments to pass to the script.
    """
    macros_dir = model.config.get("macros_path", "/var/www/html/macros")
    script_path = os.path.join(macros_dir, script_name)

    # Check if the script exists and is executable
    if not os.path.isfile(script_path):
        print(f"ERROR: Script {script_path} does not exist.")
        return False
    if not os.access(script_path, os.X_OK):
        print(f"ERROR: Script {script_path} is not executable.")
        return False

    command = [script_path] + args

    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        print(f"Script output:\n{result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Failed to execute script {script_name}. Error:\n{e.stderr}")
        return False
