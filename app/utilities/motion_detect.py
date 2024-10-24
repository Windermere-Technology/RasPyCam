import os
import numpy as np
from datetime import datetime
from core.model import CameraCoreModel


def setup_motion_pipe(md_path):
    # Get/make the directory for the motion detection FIFO pipe
    md_fifo_dir = os.path.dirname(md_path)
    if not os.path.exists(md_fifo_dir):
        os.makedirs(md_fifo_dir)
    # If the motion detection FIFO doesn't exist, create it
    if not os.path.exists(md_path):
        print(
            "ALERT: Motion detection pipe does not exist. Making new Motion pipe file."
        )
        os.mkfifo(md_path, 0o6666)


def print_to_motion_log(log_path, message):
    timestring = "{" + datetime.now().strftime("%Y/%m/%d %H:%M:%S") + "} "
    contents = timestring + message + "\n"
    motion_log = open(log_path, "a")
    motion_log.write(contents)
    motion_log.close()


def send_motion_command(path, cmd):
    """
    Writes the appropriate command code to the motion pipe file.

    Args:
        cam: CameraCoreModel instance.
        cmd: '0', '1' or '9' (stop, start, reset).
    """
    motion_fd = os.open(path, os.O_RDWR | os.O_NONBLOCK, 0o666)
    motion_file = os.fdopen(motion_fd, "w")
    if motion_file:
        motion_file.write(cmd)
        motion_file.close()


def motion_detection_thread(cams):
    """
    Motion detection function. Runs in its own thread. Uses the lores
    stream to check for motion by comparing pixels between two consecutive
    frames and finding the mean-square-error of the difference. If the
    difference is above a given threshold, reports motion.
    If there is no MSE for a given number of frames, reports motion has
    ceased.

    Adapted from the example/sample program available on Picamera2's repo here:
    https://github.com/raspberrypi/picamera2/blob/main/examples/capture_motion.py

    Args:
        cam: CameraCoreModel instance.
    """
    cam = cams[CameraCoreModel.main_camera]
    prev = None
    w, h = cam.picam2.camera_configuration()[cam.md_stream]["size"]
    print("starting motion detection thread...")
    send_motion_command(cam.config["motion_pipe"], "9")  # Reset the motion pipe.
    motion_init_count = cam.config["motion_initframes"]

    while cam.current_status != "halted":
        if cam.solo_stream_mode:
            return
        cur = cam.picam2.capture_buffer(cam.md_stream)
        cur = cur[: w * h].reshape(h, w)
        # Delay until initframes have been satisfied, unless on Monitor mode.
        if motion_init_count > 1:
            if cam.config["motion_mode"] == "monitor":
                motion_init_count = 0
            else:
                if prev:
                    if (cur == prev).all():
                        # Frame has passed
                        motion_init_count -= 1
                prev = cur
                continue
        # Main processing.
        if cam.motion_detection:
            if prev is not None:
                # Measure pixels differences between current and
                # previous frame
                mse = np.square(np.subtract(cur, prev)).mean()
                if mse > cam.config["motion_threshold"]:
                    cam.motion_still_count = 0
                    print("motion detect: ", mse)
                    if not cam.detected_motion:
                        cam.motion_active_count += 1
                        if cam.motion_active_count >= cam.config["motion_startframes"]:
                            cam.detected_motion = True
                            if cam.config["motion_mode"] == "internal":
                                send_motion_command(cam.config["motion_pipe"], "1")
                            elif cam.config["motion_mode"] == "monitor":
                                print_to_motion_log(
                                    cam.config["motion_logfile"],
                                    "Motion start detected",
                                )
                            print("Motion start detected")
                else:
                    # Increment count of still frames and set detection to
                    # false when enough frames have passed to count as no longer
                    # in motion.
                    cam.motion_active_count = 0
                    if cam.detected_motion:
                        cam.motion_still_count += 1
                        if cam.motion_still_count >= cam.config["motion_stopframes"]:
                            cam.detected_motion = False
                            if cam.config["motion_mode"] == "internal":
                                send_motion_command(cam.config["motion_pipe"], "0")
                            elif cam.config["motion_mode"] == "monitor":
                                print_to_motion_log(
                                    cam.config["motion_logfile"], "Motion stop detected"
                                )
                            print("Motion stop detected")
        prev = cur
