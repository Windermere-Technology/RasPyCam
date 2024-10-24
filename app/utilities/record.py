import os
from picamera2.outputs import FfmpegOutput, FileOutput


def start_recording(cam):
    """
    Starts video recording. Creates the output file and starts encoder in
    the Picamera2 thread.

    Args:
        cam: CameraCoreModel instance.

    Returns:
        True if not already capturing.
        False if already capturing.
    """
    if cam.capturing_video:
        cam.print_to_logfile("Already capturing. Ignore")
        return False
    cam.print_to_logfile("Capturing started")
    cam.setup_video_encoder()
    output_path = cam.make_filename(
        cam.config["video_output_path"]
    )  # Generate output file name

    file_without_ext, ext = os.path.splitext(output_path)
    if ext.lower() == ".h264":
        cam.video_encoder.output = FileOutput(
            output_path
        )  # This might be faster than transcoding to MP4, give the choice to user.
    else:
        cam.video_encoder.output = FfmpegOutput(
            output_path
        )  # Set FfmpegOutput as output for video encoding to immediately get an MP4.

    # Generate thumbnail.
    cam.generate_thumbnail("v", output_path)

    cam.picam2.start_encoder(
        cam.video_encoder, cam.video_encoder.output, name=cam.record_stream
    )  # Start the video encoder
    cam.capturing_video = True  # Update flag to indicate video is being captured
    cam.set_status("video")  # Set camera status to 'video'
    return True


def stop_recording(cam):
    """
    Stops recording. Generates the thumbnail and resets any motion detection
    flags there may have been.

    Args:
        cam: CameraCoreModel instance.

    Returns:
        True if not already stopped.
        False if already stopped.
    """
    if not cam.capturing_video:
        cam.print_to_logfile("Already stopped. Ignore")
        return False
    cam.print_to_logfile("Capturing stopped")
    if cam.video_encoder.running:  # Stop the encoder if it's running
        cam.picam2.stop_encoder()

    cam.capturing_video = False  # Update flag to indicate video capture has stopped
    cam.reset_motion_state()  # Reset motion detection
    cam.set_status("ready")  # Set camera status back to 'ready'
    return True


def toggle_cam_record(cam, status):
    """
    Starts or stops video recording based on the status provided.

    Args:
        cam: CameraCoreModel instance.
        status (bool): If True, starts recording. If False, stops recording.
    Returns:
        True or False depending on whether camera was already started/stopped
        when executing the toggle.
    """
    if status:  # Start video recording
        success = start_recording(cam)
    else:  # Stop video recording
        success = stop_recording(cam)
    return success
