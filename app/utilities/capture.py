import numpy as np
from PIL import Image


def capture_still_image(cam):
    """Capture a still image from the real camera and save it."""
    print("Taking still image with camera...")

    # Capture metadata (optional, you can remove if not used)
    metadata = cam.capture_metadata() if hasattr(cam, "capture_metadata") else {}

    # Generate the output file name
    image_path = cam.make_filename(
        cam.config["image_output_path"]
    )  # Generate output file name

    # Capture the image as an array (this captures in BGR format)
    img = cam.picam2.capture_array("main")

    # Convert BGR to RGB and save the image using PIL
    img_rgb = Image.fromarray(img[:, :, ::-1])  # Convert BGR to RGB

    cam.picam2.helpers.save(img_rgb, metadata, image_path)

    # Save a thumbnail for this image.
    cam.generate_thumbnail("i", image_path)


def capture_stitched_image(index, cams, axis):
    """
    Takes images with multiple cameras and stitches them together.
    """
    print("Taking stitched still image with cameras")

    # Capture the current frame and metadata
    metadata = cams[index].picam2.capture_metadata()
    img_arrs = []
    for cam in cams.values():
        img = cam.picam2.capture_array(cam.still_stream)
        img_arrs.append(img)

    image_path = cams[index].make_filename(
        cams[index].config["image_output_path"]
    )  # Generate output file name

    # Find biggest image along the stitching axis
    pad_axis = 1 if axis == 0 else 0
    max_dim = img_arrs[0].shape[pad_axis]
    for img in img_arrs:
        dim = img.shape[pad_axis]
        max_dim = max(dim, max_dim)

    # If sizes are different along axis, pad out the smaller ones along the relevant axis
    for idx, img in enumerate(img_arrs):
        dim = img.shape[pad_axis]
        diff = max_dim - dim
        if diff > 0:
            if axis == 0:
                # Pad horizontally.
                padding = np.zeros((img.shape[0], diff, 3), dtype=np.uint8)
                img = np.hstack((img, padding))
            else:
                # Pad vertically.
                padding = np.zeros((diff, img.shape[1], 3), dtype=np.uint8)
                img = np.vstack((img, padding))
        img_arrs[idx] = img

    # Stitch the images.
    stitched_img = img_arrs[0]
    for img in img_arrs[1:]:
        if axis == 0:
            stitched_img = np.vstack((stitched_img, img))
        else:
            stitched_img = np.hstack((stitched_img, img))

    # Save the stitched image
    stitched_image = Image.frombuffer(
        "RGB",
        (stitched_img.shape[1], stitched_img.shape[0]),
        stitched_img,
        "raw",
        "BGR",
        0,
        1,
    )
    cams[index].picam2.helpers.save(stitched_image, metadata, image_path)

    # Save a thumbnail for this image.
    cams[index].generate_thumbnail("i", image_path)
