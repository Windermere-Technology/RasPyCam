import os
import logging
from utilities import diagnostics
from picamera2.outputs import FileOutput
from utilities.video_output import RecordingOutput as FfmpegOutput


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
    diagnostics.event("recording requested")
    cam.recording_error = None
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

    if ext.lower() != ".h264":
        def output_failed(error):
            # Called on the encoder thread: let the main thread stop the encoder.
            diagnostics.event(f"FFmpeg error: {error}")
            diagnostics.incident("FFmpeg output failed")
            cam.recording_error = str(error)
            logging.error("FFmpeg recording failed for %s: %s", output_path, error)
        cam.video_encoder.output.error_callback = output_failed

    # Generate thumbnail.
    diagnostics.event(f"thumbnail start: {output_path}")
    cam.generate_thumbnail("v", output_path)
    diagnostics.event("thumbnail complete; encoder starting")

    try:
        cam.picam2.start_encoder(
            cam.video_encoder, cam.video_encoder.output, name=cam.record_stream
        )
    except Exception:
        # Preserve the original exception; cleanup handles a partially started encoder.
        cam.capturing_video = True
        raise
    cam.capturing_video = True
    diagnostics.event("encoder started")
    cam.set_status("video")
    cam.print_to_logfile("Capturing started")

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
    diagnostics.event("recording stop requested")
    try:
        if cam.video_encoder.running:
            cam.picam2.stop_encoder(cam.video_encoder)
        else:
            cam.video_encoder.output.stop()
    finally:
        cam.capturing_video = False
        cam.record_until = None
        cam.reset_motion_state()
    diagnostics.event("recording stopped")
    cam.set_status("ready")
    cam.print_to_logfile("Capturing stopped")

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
