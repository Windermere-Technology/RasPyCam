import os
import cv2
import numpy as np
from core.model import CameraCoreModel
from PIL import Image


def generate_preview(cams):
    """
    Generate a preview image from the camera request and save it to the specified preview path.
    The preview is temporarily saved and then renamed to prevent flickering issues.
    """
    # Capture the current frame and metadata based on enabled previews
    img_arrs = {}
    last_h = None
    with CameraCoreModel.preview_dict_lock:
        for index, cam in cams.items():
            if CameraCoreModel.show_previews[index]:
                if not last_h:
                    last_h = cam.picam2.camera_configuration()[cam.preview_stream][
                        "size"
                    ][1]
                if (
                    last_h
                    == cam.picam2.camera_configuration()[cam.preview_stream]["size"][1]
                ):
                    img_arrs[index] = cam.picam2.capture_array(cam.preview_stream)
    # If no previews enabled, do nothing.
    if not img_arrs:
        return

    # Setup dimensions for preview.

    preview_path = cams[CameraCoreModel.main_camera].config["preview_path"]
    preview_width = cams[CameraCoreModel.main_camera].config["preview_size"][0] * len(
        img_arrs
    )  # Preview width from config
    preview_height = cams[CameraCoreModel.main_camera].config["preview_size"][
        1
    ]  # Preview height from config

    # Create the preview image using specified dimensions
    # Convert colorspace if needed and resize to preview size.
    for cam_index in img_arrs:
        if (
            cams[cam_index].picam2.stream_configuration(
                name=cams[cam_index].preview_stream
            )["format"][:3]
            == "RGB"
        ):
            continue
        else:
            img_arrs[cam_index] = cv2.cvtColor(
                img_arrs[cam_index], cv2.COLOR_YUV420p2RGB
            )
    # Stitch images if multiple previews.
    for index, arr in enumerate(img_arrs.values()):
        if index == 0:
            img = arr
        else:
            img = np.hstack((img, arr))

    preview_img = Image.frombuffer(
        "RGB", (img.shape[1], img.shape[0]), img, "raw", "BGR", 0, 1
    )
    preview_img = preview_img.resize((preview_width, preview_height))

    # Temporarily save the preview image to avoid conflicts when updating the file
    temp_path = preview_path + ".part.jpg"

    # Save the preview image, don't use picam2.helpers, don't need metadata and it is slow AF.
    preview_img.save(
        temp_path, quality=cams[CameraCoreModel.main_camera].config["preview_quality"]
    )

    # Rename the temporary file to the actual preview path (avoids preview flickering)
    os.rename(temp_path, preview_path)
