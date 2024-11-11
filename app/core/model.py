import logging
from picamera2 import Picamera2, MappedArray
from picamera2.encoders import H264Encoder, JpegEncoder
from picamera2.outputs import FileOutput
from datetime import datetime
import libcamera
import threading
import shutil
import os
import cv2
import numpy as np


class CameraCoreModel:
    """
    The CameraCoreModel represents the core camera functionality.
    It holds the camera instance, configuration settings, and controls the camera's status and encoders.
    """

    APP_NAME = "RasPyCam"
    MAX_COMMAND_LEN = 256  # Maximum length of commands received from pipe
    FIFO_MAX = 10  # Maximum number of commands that can be queued at once
    VALID_COMMANDS = {
        "an": "annotation",
        "sh": "sharpness",
        "co": "contrast",
        "br": "brightness",
        "sa": "saturation",
        "ss": "shutter_speed",
        "ec": "exposure_compensation",
        "is": "iso",
        "qu": "image_quality",
        "ca": None,
        "px": [
            "video_width",
            "video_height",
            "video_fps",
            "MP4Box_fps",
            "image_width",
            "image_height",
        ],
        "pv": ["quality", "width", "divider", "height"],
        "im": None,
        "md": None,
        "mx": "motion_external",
        "mt": "motion_threshold",
        "ms": "motion_initframes",
        "mb": "motion_startframes",
        "me": "motion_stopframes",
        "ru": None,
        "bi": "video_bitrate",
        "sc": None,
        "fl": ["hflip", "vflip"],
        "rs": None,
        "cn": None,
        "im+im": None,
        "dp": "show_preview",
        "cr": "camera_resolution",
        "cs": None,
        "ix": None,
        "ix+ix": None,
        "1s": "solo_stream_mode",
        "wb": "white_balance",
        "ag": ["autowbgain_r", "autowbgain_b"],
        "tl": "timelapse_start_stop",
        "tv": "tl_interval",
    }

    debug_execution_time = None

    process_running = False
    main_camera = None
    fifo_fd = None  # File descriptor for the FIFO pipe
    fifo_interval = 1.00  # Time interval for checking the FIFO pipe for new commands

    command_queue = []  # Queue of commands to be executed
    cmd_queue_lock = threading.Lock()  # Lock for synchronising access to command_queue

    show_previews = (
        {}
    )  # Dict of cameras flagged to show/stitch their preview, len = total camera count
    preview_dict_lock = threading.Lock()  # Lock for syncing access to preview dict

    def __init__(self, camera_info, config_path):
        """Initialises the camera and loads the configuration."""
        self.cam_model = camera_info["Model"]
        self.cam_index = camera_info["Num"]
        self.cam_index_str = str(camera_info["Num"])
        self.picam2 = Picamera2(camera_info["Num"])
        self.config = {
            "annotation": "RPi Cam %Y.%M.%D_%h:%m:%s",
            "anno_text_scale": 2,
            "anno_text_origin": (30, 80),
            "anno_text_colour": (0, 0, 0),
            "anno_text_thickness": 5,
            "user_annotate": "/dev/shm/mjpeg/user_annotate.txt",
            "sharpness": 1.0,
            "contrast": 1.0,
            "brightness": 0.0,
            "saturation": 1.0,
            "analogue_gain": 7.0,  # This is ISO in RaspiMJPEG.
            "exposure_compensation": 0,
            "white_balance_mode": libcamera.controls.AwbModeEnum.Auto,
            "colorgains_red": 0.0,  # Used as a tuple with colorgains_blue for ColorGains.
            "colorgains_blue": 0.0,
            "rotation": 0,
            "hflip": False,
            "vflip": False,
            "exposure_time": 0,  # This is shutter speed in RaspiMJPEG.
            "preview_size": (512, 288),
            "preview_path": "/tmp/preview/cam_preview.jpg",
            "divider": 1,
            "preview_quality": 50,
            "image_output_path": "/tmp/media/im_cam%I_%i_%Y%M%D_%h%m%s.jpg",
            "lapse_output_path": "/tmp/media/tl_cam%I_%t_%i_%Y%M%D_%h%m%s.jpg",
            "video_output_path": "/tmp/media/vi_cam%I_%v_%Y%M%D_%h%m%s.mp4",
            "media_path": "/tmp/media",
            "status_file": "/tmp/status_mjpeg.txt",
            "control_file": "/tmp/FIFO",
            "motion_pipe": "/tmp/motionFIFO",
            "video_width": 1920,
            "video_height": 1080,
            "video_fps": 30,
            "video_bitrate": 17000000,  # Default video bitrate for encoding
            "mp4_fps": 30,  # Attached to the h264encoder.
            "image_width": 1920,
            "image_height": 1080,
            "image_quality": 85,
            "motion_mode": "internal",  # Equivalent of the RaspiMJPEG's motion_external setting.
            "motion_threshold": 7.0,  # Mean-Square-Error. Default value per Picamera2's sample program.
            "motion_initframes": 0,  # How many frames to delay before starting any actual motion detection
            "motion_startframes": 3,  # How many frames of motion needed before flagging as motion detected
            "motion_stopframes": 50,  # How many frames w/o motion needed before unflagging for detected motion
            "thumb_gen": "vit",  # Controls whether or not to generate thumbnails for (v)ideo, (i)mages and (t)imelapse
            "autostart": True,  # Whether to start the Picamera2 instance when program launches, without waiting for 'ru'.
            "motion_detection": False,  # Whether to auto-start Motion Detection when program launches, no effect unless autostart is true.
            "user_config": "/tmp/uconfig",  # User configuration file used by RPi Cam Web Interface to overwrite defaults.
            "log_file": "/tmp/scheduleLog.txt",  # Filepath to record "print_to_log()" messages.
            "log_size": 5000,  # Set to 0 to not write to log file.
            "motion_logfile": "/tmp/motionLog.txt",  # Log file recording motion events during Monitor mode.
            "picam_buffer_count": 2,
            "solo_stream_mode": False,
            "tl_interval": 30, # timelapse interval in seconds
        }

        self.write_to_config = (
            {}
        )  # Dict to store settings to write into the user_config file.

        # Set up internal flags.
        self.current_status = (
            "halted"  # Holds the current status string of the camera system
        )

        self.show_preview = (
            True  # Whether or not to show/stitch feed onto preview image output
        )

        self.still_image_index = 0  # Next image file index, based on count of image files in output directory.
        self.video_file_index = 0  # Next video file index, based on count of video files in output directory.
        self.timelapse_index = 0  # Next timelapse file index, based on highest timelapse index found in the thumbnails in output directory.
        self.capturing_still = (
            False  # Flag for whether still image capture is in progress
        )
        self.capturing_video = False  # Flag for whether video recording is in progress
        self.record_until = (
            None  # Time at which to stop recording. None or 0 means no timer.
        )

        self.sensor_format = (1920, 1080)
        self.solo_stream_mode = self.config[
            "solo_stream_mode"
        ]  # Flag for whether to use main stream only.
        self.motion_detection = False  # Flag for motion detection mode status

        self.timelapse_on = False  # Flag for timelapse mode
        self.timelapse_count = 0 # Clear timelapse sequence number
        self.detected_motion = False  # Flag for whether motion has been detected by MD.
        self.motion_still_count = (
            0  # Counter for number of consecutive frames with no motion.
        )
        self.motion_active_count = (
            0  # Counter for number of consecutive frames with active motion.
        )

        # Remembers the provided config path for user config reset.
        self.default_config_path = config_path

        self.read_config_file(
            config_path
        )  # Loads config from the provided config file path

        self.make_logfile_directories()

        self.read_config_file(
            self.config["user_config"]
        )  # Loads starting configs from the specified config file.
        self.read_user_config()  # Loads user configs to dict to write back.

        # Turn off the preview by default if on solo stream mode.
        if self.config["solo_stream_mode"]:
            self.show_preview = False

        self.make_output_directories()

        # Set image/video file indexes based on detected thumbnail counts in the folder(s).
        self.make_filecounts()

        # Print camera hardware information.
        print("Sensor Modes:")
        print(self.picam2.sensor_modes)
        print("Max Sensor Resolution:")
        print(self.picam2.sensor_resolution)

        # Create and configure the camera for video capture
        self.still_stream = "main"
        if self.config["solo_stream_mode"]:
            # Preview and video record on the main stream.
            self.toggle_solo_stream_mode(True)
        else:
            # Preview and video record on the lores stream.
            self.toggle_solo_stream_mode(False)
        self.video_config = None
        self.build_configuration_object()

        # Print configuration information.
        print(self.picam2.camera_controls)
        print(self.picam2.camera_configuration())

        self.video_encoder = None  # Initialise video encoder as None
        self.setup_encoders()  # Sets up JPEG and H264 encoders for image and video encoding
        self.picam2.pre_callback = (
            self.setup_pre_callback
        )  # Assign function for pre-callback

        # Set default adjustable settings
        self.refresh_all_adjustable_settings()
        print(self.picam2.camera_controls)

        # Set initial status of the camera depending on autostart flag
        if self.config["autostart"]:
            self.current_status = "ready"
            self.picam2.start()
            # Set initial status of motion detection
            if self.config["motion_detection"]:
                self.motion_detection = True
        else:
            print("no autostart")

        # Set AutoFocus for Arducam: https://docs.arducam.com/Raspberry-Pi-Camera/Native-camera/PiCamera2-User-Guide/
        # 0 = Manual, 1 = Auto, 2 = Continuous
        # For manual, takes LenPosition as a parameter: self.picam2.set_controls({"AfMode": 0, "LensPosition": 5})
        if self.cam_model == "ov64a40":
            self.picam2.set_controls({"AfMode": 1, "AfTrigger": 0})

    def setup_pre_callback(self, request):
        """
        Function assigned to apply changes to images pre-callback.
        Used for User Annotations.
        """
        if self.config["annotation"]:
            if not self.solo_stream_mode:
                with MappedArray(request, "lores") as m:
                    cv2.putText(
                        img=m.array,
                        text=self.make_filename(self.config["annotation"]),
                        org=self.config["anno_text_origin"],
                        fontFace=cv2.FONT_HERSHEY_SIMPLEX,
                        fontScale=self.config["anno_text_scale"],
                        color=self.config["anno_text_colour"],
                        thickness=self.config["anno_text_thickness"],
                    )
            with MappedArray(request, "main") as m:
                cv2.putText(
                    img=m.array,
                    text=self.make_filename(self.config["annotation"]),
                    org=self.config["anno_text_origin"],
                    fontFace=cv2.FONT_HERSHEY_SIMPLEX,
                    fontScale=self.config["anno_text_scale"],
                    color=self.config["anno_text_colour"],
                    thickness=self.config["anno_text_thickness"],
                )

    def restart(self, reload_config=False):
        """Restarts the Picamera2 instance."""
        self.picam2.stop()
        if reload_config:
            self.read_config_file(self.config["user_config"])
            self.make_output_directories()
            self.make_filecounts()
            self.build_configuration_object()
        self.picam2.start()
        self.current_status = "ready"

    def stop_all(self):
        """Stops the Picamera2 instance and any encoders currently running."""
        if self.video_encoder.running:
            self.picam2.stop_encoder(self.video_encoder)
        if self.picam2.started:
            self.picam2.stop()
        self.reset_motion_state()
        self.capturing_video = False
        self.capturing_still = False
        self.motion_detection = False
        self.timelapse_on = False

    def reset_motion_state(self):
        """Resets the internal state flags for motion detection."""
        self.detected_motion = False
        self.motion_still_count = 0
        self.motion_active_count = 0

    def teardown(self):
        """Stops and closes the camera when shutting down."""
        if self.video_encoder.running:
            self.picam2.stop_encoder(self.video_encoder)
        self.picam2.stop()
        self.picam2.close()
        # Remove any preview images there may be in the directory.
        preview_img = self.config["preview_path"]
        preview_part = preview_img + ".part.jpg"
        if os.path.exists(preview_img):
            os.remove(preview_img)
        if os.path.exists(preview_part):
            os.remove(preview_part)
        self.print_to_logfile(
            f"Shut down Picamera2 instance for camera {self.cam_index_str}"
        )

    def make_logfile_directories(self):
        """
        Makes directories and files for logs and userconfig if they don't exist.
        """
        logs = [
            self.config["user_config"],
            self.config["log_file"],
            self.config["motion_logfile"],
        ]
        for log in logs:
            dirpath = os.path.dirname(log)
            if not os.path.exists(dirpath):
                os.makedirs(dirpath)
            if not os.path.exists(log):
                logfile = open(log, "a")
                logfile.close()

    def make_output_directories(self):
        """
        Makes directories for status file, media folder, video, image and
        timelapse output files if they don't exist.
        """
        preview_path = os.path.dirname(self.config["preview_path"])
        im_path = os.path.dirname(self.config["image_output_path"])
        tl_path = os.path.dirname(self.config["lapse_output_path"])
        video_path = os.path.dirname(self.config["video_output_path"])
        media_path = os.path.dirname(self.config["media_path"])
        status_path = os.path.dirname(self.config["status_file"])
        paths = [preview_path, im_path, tl_path, video_path, media_path, status_path]
        for path in paths:
            if not os.path.exists(path):
                os.makedirs(path)

    def build_configuration_object(self):
        """
        Builds the video_config object for the camera to use.
        """
        # Note: The number of buffers available appears to depend on the total max resolution
        # configured for all available cameras.
        print(f"Building camera config object for camera {self.cam_index}:")

        main_size = (self.config["image_width"], self.config["image_height"])
        lores_size = (self.config["video_width"], self.config["video_height"])

        # Begin checks to ensure main stream size maxes out at the camera's best resolution.
        # Ensure lores stream size maxes out at the camera's best resolution.
        if main_size[0] > self.picam2.sensor_resolution[0]:
            main_size = (self.picam2.sensor_resolution[0], main_size[1])
        if main_size[1] > self.picam2.sensor_resolution[1]:
            main_size = (main_size[0], self.picam2.sensor_resolution[1])
        if lores_size[0] > main_size[0]:
            lores_size = (main_size[0], lores_size[1])
        if lores_size[1] > main_size[1]:
            lores_size = (lores_size[0], main_size[1])
        if self.solo_stream_mode:
            self.video_config = self.picam2.create_video_configuration(
                buffer_count=self.config["picam_buffer_count"],
                # Default is 6 for video_config, but anything above 2 crashes with Owlsight cam's full 9248x6440 resolution.
                # If using 2 cameras at once, can only use 1 at a time.
                display=None,
                queue=False,
                main={
                    "size": main_size,
                    "format": "RGB888",
                },
                raw={
                    "size": self.sensor_format,
                },
            )
        else:
            self.video_config = self.picam2.create_video_configuration(
                buffer_count=self.config["picam_buffer_count"],
                display=None,
                main={
                    "size": main_size,
                    "format": "RGB888",
                },
                lores={"size": lores_size, "format": "YUV420"},
                raw={
                    "size": self.sensor_format,
                },
            )
        # Apply other settings.
        self.video_config["transform"] = libcamera.Transform(
            hflip=self.config["hflip"], vflip=self.config["vflip"]
        )
        self.picam2.options["quality"] = self.config["image_quality"]
        # Aligning improves performance by changing stream sizes to fit the nearest
        # number most easily processed by the camera/ISP (i.e. from 1924x1082 to 1920x1080).
        self.picam2.align_configuration(self.video_config)
        # Apply new configuration.
        self.picam2.configure(self.video_config)
        # Snap sensor_format recorded value to actual sensor_mode size.
        if "raw" in self.picam2.camera_config:
            self.sensor_format = self.picam2.camera_config["raw"]["size"]
        # Disable Raw Stream if in Single-Stream Mode
        if self.solo_stream_mode:
            self.picam2.video_configuration.enable_raw(False)

    def toggle_solo_stream_mode(self, switch_on):
        if switch_on:
            self.solo_stream_mode = True
            self.config["picam_buffer_count"] = 1
            self.preview_stream = "main"
            self.record_stream = "main"
            self.md_stream = "main"
        else:
            self.solo_stream_mode = False
            self.preview_stream = "lores"
            self.record_stream = "lores"
            self.md_stream = "raw"

    def set_camera_configuration(self, cmd_code, cmd_param):
        """
        Sets any configuration settings belonging to picam2.camera_configuration dicts.
        That is, any settings requiring the camera to be stopped and restarted to take effect.

        Returns:
            True if no errors in parsing the parameters, otherwise False.
        """
        if cmd_code == "px":
            logging.info("Changing general settings: " + cmd_param)
            # Parameters: vw vh vfps boxfps iw ih vdivider
            # We ignore vdivider, this isn't used with Picamera2.
            settings = cmd_param.split(" ")
            try:
                self.config["video_width"] = int(settings[0])
                self.config["video_height"] = int(settings[1])
                self.config["video_fps"] = int(settings[2])
                self.config["mp4_fps"] = int(settings[3])
                self.config["image_width"] = int(settings[4])
                self.config["image_height"] = int(settings[5])
            except ValueError:
                logging.error("Error: Invalid settings parameters.")
                return False
        elif cmd_code == "fl":
            # Flip. 0: hflip=0, vflip=0; 1: hflip=1, vflip=0; 2: hflip=0, vflip=1; 4: hflip=1, vflip=1
            logging.info("Flip set mode " + cmd_param)
            if cmd_param == "1":
                hf = 1
                vf = 0
            elif cmd_param == "2":
                hf = 0
                vf = 1
            elif cmd_param == "3":
                hf = 1
                vf = 1
            else:
                # Mode was either 0 or some other value.
                hf = 0
                vf = 0
            self.config["hflip"] = hf
            self.config["vflip"] = vf
        if cmd_code == "cr":
            # Change Resolution/Camera Resolution
            logging.info(f"Changing camera {self.cam_index} resolution")
            params = cmd_param.split(" ")
            if (not params) or (len(params) < 2):
                logging.error("ERROR: Not enough parameters.")
                return False
            try:
                w = int(params[0])
                h = int(params[1])
                self.sensor_format = (w, h)
            except ValueError:
                logging.error("Error: Invalid resolution parameters.")
                return False
            self.sensor_format = (w, h)
        if cmd_code == "cs":
            # Change image/video stream sizes.
            logging.info(f"Changing {self.cam_index} image/video stream sizes")
            params = cmd_param.split(" ")
            if (not params) or (len(params) < 3):
                logging.error("ERROR: Not enough parameters.")
                return False
            try:
                w1 = self.sensor_format[0] if params[1] == "=" else int(params[1])
                h1 = self.sensor_format[1] if params[2] == "=" else int(params[2])
            except ValueError:
                logging.error("Error: Invalid resolution parameters.")
                return False
            if params[0] == "i":
                self.config["image_width"] = w1
                self.config["image_height"] = h1
            elif params[0] == "v":
                self.config["video_width"] = w1
                self.config["video_height"] = h1
            elif (params[0] == "i+v") or (params[0] == "v+i"):
                if len(params) < 5:
                    logging.error("ERROR: Not enough parameters.")
                    return False
                try:
                    w2 = self.sensor_format[0] if params[3] == "=" else int(params[3])
                    h2 = self.sensor_format[1] if params[4] == "=" else int(params[4])
                except ValueError:
                    logging.error("Error: Invalid resolution parameters.")
                    return False
                self.config["image_width"] = w1
                self.config["image_height"] = h1
                self.config["video_width"] = w2
                self.config["video_height"] = h2
            else:
                logging.error("Error: Invalid target for size change.")
                return False
        if cmd_code == "ix":
            # Parameters for this do not need validation.
            w = cmd_param[0][0]
            h = cmd_param[0][1]
            self.config["image_width"] = w
            self.config["image_height"] = h
            self.sensor_format = (w, h)
            logging.info(cmd_param)
            logging.info(self.sensor_format)
            self.config["picam_buffer_count"] = cmd_param[0][2]
            if cmd_param[1] == 0:
                logging.info("Capturing still image at maximum sensor resolution")
                self.toggle_solo_stream_mode(True)
            else:
                logging.info("Reverting from maximum sensor resolution")
                self.toggle_solo_stream_mode(False)
        if cmd_code == "1s":
            if cmd_param == "1":
                self.toggle_solo_stream_mode(True)
                self.show_preview = False
            if cmd_param == "2":
                self.sensor_format = (
                    self.picam2.sensor_resolution[0],
                    self.picam2.sensor_resolution[1],
                )
                self.toggle_solo_stream_mode(True)
                self.show_preview = False
            else:
                self.toggle_solo_stream_mode(False)
        if cmd_code == "rs":
            logging.info("Resetting user configurations file")
            self.reset_user_configs()
        # Create new configuration object from updated model settings
        self.build_configuration_object()
        return True

    def set_motion_params(self, cmd_code, cmd_param):
        """
        Sets the motion parameters based on command received:
        cmd_code:
            mt : Threshold
            ms : Initframes
            mb : Startframes
            me : Stopframes
        cmd_params:
            Must be an integer value.

        Returns:
            True if no problems in parsing cmd_params, otherwise False.
        """
        value = 0
        try:
            value = int(cmd_param)
        except ValueError:
            print("ERROR: Value is not an integer")
            return False
        if value < 0:
            value = 0  # Can't have less than 0 frames.
        if cmd_code == "mt":
            # Do linear scaling to turn vector count into MSE.
            self.config["motion_threshold"] = value / (250 / 7)
        elif cmd_code == "ms":
            self.config["motion_initframes"] = value
        elif cmd_code == "mb":
            self.config["motion_startframes"] = value
        elif cmd_code == "me":
            self.config["motion_stopframes"] = value
        return True

    def setup_encoders(self):
        """Sets up the JPEG and H264 encoders for the camera."""
        self.setup_jpeg_encoder()
        self.setup_video_encoder()

    def setup_jpeg_encoder(self):
        """
        Sets up the JPEG encoder for outputting stills.
        """
        self.jpeg_encoder = JpegEncoder(
            q=self.config["image_quality"]
        )  # JPEG encoder for still images
        self.jpeg_encoder.output = FileOutput()  # Output destination for JPEG images

    def setup_video_encoder(self):
        """
	Setup the encoder used for recording video (H264).
        """
        self.video_encoder = H264Encoder(
            bitrate=self.config["video_bitrate"], framerate=self.config["mp4_fps"]
        )
        self.video_encoder.size = self.picam2.camera_config[self.record_stream]["size"]
        self.video_encoder.format = self.picam2.camera_config[self.record_stream][
            "format"
        ]

    def read_config_file(self, config_path):
        """Reads the configuration file and loads it into the model."""
        if not config_path:
            print("No configuration file provided. Using hardcoded defaults.")
            return
        configs_from_file = {}
        # Parse each non-comment line in the configuration file
        with open(config_path, "r") as cf_file:
            for line in cf_file:
                strippedline = line.strip()
                if strippedline and strippedline[0] != "#":
                    setting = strippedline.split()
                    key, value = setting[0], " ".join(setting[1:])
                    configs_from_file[key] = value if value else None
        self.process_configs_from_file(
            configs_from_file
        )  # Process the parsed configuration

    def process_configs_from_file(self, parsed_configs):
        """Processes the parsed configurations and applies them to the model.
        Updates model configuration values with values parsed from the config file
        """
        # Parse annotation configurations.
        if "annotation" in parsed_configs:
            self.config["annotation"] = parsed_configs["annotation"]
        if "anno_text_scale" in parsed_configs:
            self.config["anno_text_scale"] = int(parsed_configs["anno_text_scale"])
        if "anno_text_origin" in parsed_configs:
            origins = parsed_configs["anno_text_origin"].split(" ")
            x = int(origins[0])
            y = int(origins[1])
            self.config["anno_text_origin"] = (x, y)
        if "anno_text_colour" in parsed_configs:
            colours = parsed_configs["anno_text_colour"].split(" ")
            r = int(colours[0])
            g = int(colours[1])
            b = int(colours[2])
            self.config["anno_text_colour"] = (r, g, b)
        if "anno_text_thickness" in parsed_configs:
            self.config["anno_text_thickness"] = int(
                parsed_configs["anno_text_thickness"]
            )

        # Parse the user annotation file path.
        if "user_annotate" in parsed_configs:
            self.config["user_annotate"] = parsed_configs["user_annotate"]

        # Parse general camera configuration settings,
        if "sharpness" in parsed_configs:
            # Need to scale. RaspiMJPEG uses -100 to 100 default 0,
            # but Picam2 uses 0 to 16.0 default 1.0.
            # We will scale the positive values between 1 to 100 and negative values between 0 and 1.0.
            sharpness = int(parsed_configs["sharpness"])
            if sharpness == 0:
                sharpness = 1
            elif sharpness > 0:
                sharpness = 1 + ((sharpness * 15) / 100)
            else:
                sharpness = 1 - (sharpness / -100)
            sharpness = 0 if sharpness < 0 else sharpness
            self.config["sharpness"] = sharpness
        if "contrast" in parsed_configs:
            # Same scaling as Saturation. RaspiMJPEG uses -100 to 100 default 0,
            # but Picam2 uses 0 to 32.0 default 1.0.
            # We will scale the positive values between 1 to 100 and negative values between 0 and 1.0.
            contrast = int(parsed_configs["contrast"])
            if contrast == 0:
                contrast = 1
            elif contrast > 0:
                contrast = 1 + ((contrast * 31) / 100)
            else:
                contrast = 1 - (contrast / -100)
            contrast = 0 if contrast < 0 else contrast
            self.config["contrast"] = contrast
        if "brightness" in parsed_configs:
            # Need to scale. RaspiMJPEG uses 0-100 default 50,
            # but Picam2 uses -1.0 to 1.0 default 0.
            brightness = ((int(parsed_configs["brightness"]) * 2) - 100) / 100
            self.config["brightness"] = brightness
        if "saturation" in parsed_configs:
            # Same scaling as Contrast. RaspiMJPEG uses -100 to 100 default 0,
            # but Picam2 uses 0 to 32.0 default 1.0.
            # We will scale the positive values between 1 to 100 and negative values between 0 and 1.0.
            saturation = int(parsed_configs["saturation"])
            if saturation == 0:
                saturation = 1
            elif saturation > 0:
                saturation = 1 + ((saturation * 31) / 100)
            else:
                saturation = 1 - (saturation / -100)
            saturation = 0 if saturation < 0 else saturation
            self.config["saturation"] = saturation
        if "exposure_compensation" in parsed_configs:
            # Need to scale. RaspiMJPEG uses -10 to 10 default 0,
            # but Picam2 uses -8.0 to 8.0 default 0.
            exposure_val = (int(parsed_configs["exposure_compensation"]) * 8) / 10
            self.config["exposure_compensation"] = exposure_val
        if "white_balance" in parsed_configs:
            enum_dict = {
                "auto": libcamera.controls.AwbModeEnum.Auto,
                "tungsten": libcamera.controls.AwbModeEnum.Tungsten,
                "fluorescent": libcamera.controls.AwbModeEnum.Fluorescent,
                "daylight": libcamera.controls.AwbModeEnum.Daylight,
                "cloudy": libcamera.controls.AwbModeEnum.Cloudy,
                "indoor": libcamera.controls.AwbModeEnum.Indoor,
                "incandescent": libcamera.controls.AwbModeEnum.Indoor,
                "shade": libcamera.controls.AwbModeEnum.Auto,  # Libcamera has no Shade option.
            }
            mode = parsed_configs["white_balance"].lower()
            if mode in enum_dict:
                self.config["white_balance_mode"] = enum_dict[mode]
        if "autowbgain_r" in parsed_configs:
            self.config["colorgains_red"] = float(parsed_configs["autowbgain_r"]) / 100
        if "autowbgain_b" in parsed_configs:
            self.config["colorgains_blue"] = float(parsed_configs["autowbgain_b"]) / 100
        if "rotation" in parsed_configs:
            # We only want to accept multiples of 90 and really only care about 90, 180 and 270.
            # Does not work, needs special method to transpose YUV and RGB arrays for pre-callback.
            rotation = int(parsed_configs["rotation"]) % 360
            if (rotation % 90) == 0:
                self.config["rotation"] = rotation
        if "hflip" in parsed_configs:
            self.config["hflip"] = (
                True if parsed_configs["hflip"].lower() == "true" else False
            )
        if "vflip" in parsed_configs:
            self.config["vflip"] = (
                True if parsed_configs["vflip"].lower() == "true" else False
            )
        if "shutter_speed" in parsed_configs:
            self.config["exposure_time"] = int(parsed_configs["shutter_speed"])

        # Parse FIFO pipe file and status file settings.
        if "status_file" in parsed_configs:
            if parsed_configs["status_file"]:
                self.config["status_file"] = parsed_configs["status_file"]
        if "control_file" in parsed_configs:
            if parsed_configs["control_file"]:
                self.config["control_file"] = parsed_configs["control_file"]
        if "motion_pipe" in parsed_configs:
            if parsed_configs["motion_pipe"]:
                self.config["motion_pipe"] = parsed_configs["motion_pipe"]
        if "fifo_interval" in parsed_configs:
            CameraCoreModel.fifo_interval = (
                int(parsed_configs["fifo_interval"]) / 1000000
            )

        # Parse output filepath settings.
        if "preview_path" in parsed_configs:
            self.config["preview_path"] = parsed_configs["preview_path"]
        if "media_path" in parsed_configs:
            self.config["media_path"] = parsed_configs["media_path"]
        if "image_path" in parsed_configs:
            self.config["image_output_path"] = parsed_configs["image_path"]
        if "lapse_path" in parsed_configs:
            self.config["lapse_output_path"] = parsed_configs["lapse_path"]
        if "video_path" in parsed_configs:
            self.config["video_output_path"] = parsed_configs["video_path"]

        # Parse output resolution/size and bitrate settings.
        if "width" in parsed_configs:
            parsed_preview_width = int(parsed_configs["width"])
            # Allow height to be specified, default to 16:9 if not
            preview_height = int(
                parsed_configs.get("height", (parsed_preview_width / 16) * 9)
            )
            self.config["preview_size"] = (parsed_preview_width, preview_height)
        if "quality" in parsed_configs:
            self.config["preview_quality"] = int(parsed_configs["quality"])
        if "divider" in parsed_configs:
            self.config["divider"] = int(parsed_configs["divider"])
        if "video_width" in parsed_configs:
            self.config["video_width"] = int(parsed_configs["video_width"])
        if "video_height" in parsed_configs:
            self.config["video_height"] = int(parsed_configs["video_height"])
        if "video_fps" in parsed_configs:
            self.config["video_fps"] = int(parsed_configs["video_fps"])
        if "video_bitrate" in parsed_configs:
            self.config["video_bitrate"] = int(parsed_configs["video_bitrate"])
        if (
            "MP4Box_fps" in parsed_configs
        ):  # Not really MP4Box, but use this for H264 encoder.
            self.config["mp4_fps"] = int(parsed_configs["MP4Box_fps"])

        # Parse still image settings.
        if "image_width" in parsed_configs:
            self.config["image_width"] = int(parsed_configs["image_width"])
        if "image_height" in parsed_configs:
            self.config["image_height"] = int(parsed_configs["image_height"])
        if "image_quality" in parsed_configs:
            self.config["image_quality"] = int(parsed_configs["image_quality"])

        # Parse motion detection settings.
        if "motion_external" in parsed_configs:
            # 0 = Internal, 1 = External (motion app), 2 = Monitor (print to log)
            # No implementation for External mode yet.
            code = parsed_configs["motion_external"]
            mode = "internal"
            if code == "2":
                mode = "monitor"
            self.config["motion_mode"] = mode
        if "motion_threshold" in parsed_configs:
            # Need to do some scaling since MSE is not the same as vector count.
            # RaspiMJPEG's default threshold is >250 vector difference, Picam2's default threshold is >7 MSE.
            # For now, we just scale linearly such that 1 MSE == 250/7 vectors.
            threshold = int(parsed_configs["motion_threshold"]) / (250 / 7)
            self.config["motion_threshold"] = threshold
        if "motion_initframes" in parsed_configs:
            self.config["motion_initframes"] = int(parsed_configs["motion_initframes"])
        if "motion_startframes" in parsed_configs:
            self.config["motion_startframes"] = int(
                parsed_configs["motion_startframes"]
            )
        if "motion_stopframes" in parsed_configs:
            self.config["motion_stopframes"] = int(parsed_configs["motion_stopframes"])

        # Set thumbnail generation inclusions. If the letter v, i or t appears in the string,
        # will make thumbnails for (v)ideos, (i)mages and/or (t)imelapses when captured. If not,
        # they won't get one (this will, however, make them not show up on RPi Cam Web Interface).
        if "thumb_gen" in parsed_configs:
            self.config["thumb_gen"] = parsed_configs["thumb_gen"]

        # Set autostart and motion auto-start configs. Autostart values can be 'standard' or 'idle'.
        # We'll map them to True/False here and assume any value apart from 'standard' is False.
        if "autostart" in parsed_configs:
            self.config["autostart"] = False
            if parsed_configs["autostart"] == "standard":
                self.config["autostart"] = True
        if "motion_detection" in parsed_configs:
            if parsed_configs["motion_detection"].lower() == "true":
                self.config["motion_detection"] = True

        # Set the user configuration file.
        if "user_config" in parsed_configs:
            if parsed_configs["user_config"]:
                self.config["user_config"] = parsed_configs["user_config"]

        # Parse log file settings.
        if "log_file" in parsed_configs:
            if parsed_configs["log_file"]:
                self.config["log_file"] = parsed_configs["log_file"]
        if "log_size" in parsed_configs:
            self.config["log_size"] = int(parsed_configs["log_size"])
        if "motion_logfile" in parsed_configs:
            if parsed_configs["motion_logfile"]:
                self.config["motion_logfile"] = parsed_configs["motion_logfile"]

        # Non-RaspiMJPEG settings/RasPyCam specific settings, mostly multi-cam-related.
        if "show_preview" in parsed_configs:
            if parsed_configs["show_preview"].lower() == "false":
                self.show_preview = False
        if "picam_buffer_count" in parsed_configs:
            self.config["picam_buffer_count"] = int(
                parsed_configs["picam_buffer_count"]
            )
        if "camera_resolution" in parsed_configs:
            resolution = parsed_configs["camera_resolution"].split(" ")
            width = int(resolution[0])
            height = int(resolution[1])
            self.sensor_format = (width, height)
        if "solo_stream_mode" in parsed_configs:
            if parsed_configs["solo_stream_mode"].lower() == "true":
                self.config["solo_stream_mode"] = True
            else:
                self.config["solo_stream_mode"] = False

    def read_user_config(self):
        """Loads the settings for the user config file into the write_to_configs dict
        in order to ready for writing into the file.
        """
        config_path = self.config["user_config"]
        with open(config_path, "r") as cf_file:
            for line in cf_file:
                strippedline = line.strip()
                if strippedline and strippedline[0] != "#":
                    setting = strippedline.split()
                    key, value = setting[0], " ".join(setting[1:])
                    self.write_to_config[key] = value if value else None

    def set_image_adjustment(self, adjustment_type, value):
        """Adjusts camera's sharpness, contrast, brightness, or saturation.

        Returns:
            True if no errors in parsing the parameters, otherwise False.
        """
        if adjustment_type == "Sharpness":
            if value == 0:
                value = 1
            elif value > 0:
                value = 1 + ((value * 15) / 100)
            else:
                value = 1 - (value / -100)
            value = max(0.0, min(16.0, value))
            self.config["sharpness"] = value
        elif adjustment_type == "Contrast":
            if value == 0:
                value = 1
            elif value > 0:
                value = 1 + ((value * 31) / 100)
            else:
                value = 1 - (value / -100)
            value = max(0.0, min(32.0, value))
            self.config["contrast"] = value
        elif adjustment_type == "Brightness":
            value = ((value * 2) - 100) / 100
            value = max(-1.0, min(1.0, value))
            self.config["brightness"] = value
        elif adjustment_type == "Saturation":
            if value == 0:
                value = 1
            elif value > 0:
                value = 1 + ((value * 31) / 100)
            else:
                value = 1 - (value / -100)
            value = max(0.0, min(32.0, value))
            self.config["saturation"] = value
        elif adjustment_type == "ExposureValue":
            value = (value * 8) / 10
            value = max(-8.0, min(8.0, value))
            self.config["exposure_compensation"] = value
        elif adjustment_type == "ExposureTime":
            self.config["exposure_time"] = value
        elif adjustment_type == "AnalogueGain":
            value = value / 100
            self.config["analogue_gain"] = float(value)
        elif adjustment_type == "ColourGains":
            try:
                red_gain, blue_gain = map(float, value.strip().split(" "))
                red_gain = red_gain / 100
                blue_gain = blue_gain / 100
                self.config["colorgains_red"] = max(0.0, min(32.0, red_gain))
                self.config["colorgains_blue"] = max(0.0, min(32.0, blue_gain))
                value = (self.config["colorgains_red"], self.config["colorgains_blue"])
            except ValueError:
                print(
                    f"ERROR: Invalid color gains format: {value}. Expected format: red_gain,blue_gain"
                )
                return False
        elif adjustment_type == "AwbMode":
            mode = value.lower()
            enum_dict = {
                "auto": libcamera.controls.AwbModeEnum.Auto,
                "tungsten": libcamera.controls.AwbModeEnum.Tungsten,
                "fluorescent": libcamera.controls.AwbModeEnum.Fluorescent,
                "daylight": libcamera.controls.AwbModeEnum.Daylight,
                "cloudy": libcamera.controls.AwbModeEnum.Cloudy,
                "indoor": libcamera.controls.AwbModeEnum.Indoor,
                "incandescent": libcamera.controls.AwbModeEnum.Indoor,
                "shade": libcamera.controls.AwbModeEnum.Auto,
                "horizon": libcamera.controls.AwbModeEnum.Auto,
                "greyworld": libcamera.controls.AwbModeEnum.Auto,
                "flash": libcamera.controls.AwbModeEnum.Auto,
                # Libcamera has no pre-defined Shade, Horizon, Greyworld or Flash options.
            }
            if mode in enum_dict:
                self.config["white_balance_mode"] = enum_dict[mode]
                value = self.config["white_balance_mode"]
            else:
                print(f"ERROR: Invalid white balance mode: {value}")
                return False
        else:
            print(f"ERROR: Invalid adjustment type: {adjustment_type}")
            return False
        self.picam2.set_controls({adjustment_type: value})
        return True

    def refresh_all_adjustable_settings(self):
        """
        Sets all adjustable picam2 control settings according to what
        is in the configs dict. Currently does not do this for ColourGains, due
        to RPi Cam Web Interface's default of 150 looking pretty bad on startup.

        Also does not do this for ISO ("AnalogGain").
        """
        adjustable_settings = {
            "Sharpness": self.config["sharpness"],
            "Contrast": self.config["contrast"],
            "Brightness": self.config["brightness"],
            "Saturation": self.config["saturation"],
            "AwbMode": self.config["white_balance_mode"],
            "ExposureTime": self.config["exposure_time"],
            "FrameRate": self.config["video_fps"],
        }
        for key, item in adjustable_settings.items():
            self.picam2.set_controls({key: item})

    def capture_request(self):
        """Wrapper for capturing a camera request."""
        return self.picam2.capture_request()

    def set_status(self, status=None):
        """
        Sets the current status of the camera.
        Logic for handling transitions between various camera statuses adapted
        from RaspiMJPEG's RaspiMUtils.c updateStatus() function.
        """
        if status:
            if not self.current_status:
                self.current_status = status
                return
            if status.startswith("Error"):
                self.current_status = status
                return
        if status == "halted":
            self.current_status = "halted"
        elif not self.picam2.started:
            self.current_status = "halted"
        elif self.capturing_still:
            self.current_status = "image"
        elif self.capturing_video:
            if self.motion_detection:
                if self.timelapse_on:
                    self.current_status = "tl_md_video"
                else:
                    self.current_status = "md_video"
            else:
                if self.timelapse_on:
                    self.current_status = "tl_video"
                else:
                    self.current_status = "video"
        else:
            if self.motion_detection:
                if self.timelapse_on:
                    self.current_status = "tl_md_ready"
                else:
                    self.current_status = "md_ready"
            else:
                if self.timelapse_on:
                    self.current_status = "timelapse"
                else:
                    self.current_status = "ready"

    def make_filename(self, name):
        """Generates a file name based on the given naming scheme.
        Also used for generating the annotation text, to allow for timestamps.
        """
        current_dt = datetime.now()  # Get the current date and time
        # Format various components of the filename such as date, time, and indices
        year_2d = ("%04d" % current_dt.year)[2:]
        year_4d = "%04d" % current_dt.year
        month = "%02d" % current_dt.month
        day = "%02d" % current_dt.day
        hour = "%02d" % current_dt.hour
        minute = "%02d" % current_dt.minute
        seconds = "%02d" % current_dt.second
        millisecs = "%03d" % round(current_dt.microsecond / 1000)
        img_index = "%04d" % self.still_image_index
        vid_index = "%04d" % self.video_file_index
        tl_index = "%04d" % self.timelapse_index

        name = name.replace("%v", vid_index)
        name = name.replace("%i", img_index)
        name = name.replace("%t", tl_index)
        name = name.replace("%y", year_2d)
        name = name.replace("%Y", year_4d)
        name = name.replace("%M", month)
        name = name.replace("%D", day)
        name = name.replace("%h", hour)
        name = name.replace("%m", minute)
        name = name.replace("%s", seconds)
        name = name.replace("%u", millisecs)
        name = name.replace("%I", self.cam_index_str)

        user_annotation = self.read_annotation_file()
        name = name.replace("%a", user_annotation)

        return name.replace("%%", "%")

    def make_filecounts(self):
        """Find the counts of all types of output files in their directory and
        updates the config dict with them.... in theory. RaspiMJPEG actually does this
        a somewhat boneheaded way by not actually looking at the files themselves,
        but instead their thumbnails and extracts the type/count from the filenames of
        those, by looking at the highest existing number for the type."""
        image_count = 0
        video_count = 0
        timelapse_count = 0
        # Find all thumbnails.
        all_files = os.listdir(os.path.dirname(self.config["image_output_path"]))
        all_files.extend(os.listdir(os.path.dirname(self.config["video_output_path"])))
        all_files = set(all_files)

        for f in all_files:
            # Strip the .jpg extension off.
            filename = os.path.basename(f)
            file_without_ext, ext = os.path.splitext(filename)
            # If the extensionless filename now ends with '.th', it is a thumbnail.
            if file_without_ext.endswith(".th"):
                # Strip the .th extension off, then attempt to strip the type+count portion off.
                without_th = os.path.splitext(file_without_ext)[0]
                typecount = os.path.splitext(without_th)
                filetype = typecount[1][1:2]
                filecount = typecount[1][2:]
                count = 0
                # Skip any invalid filenames.
                try:
                    count = int(filecount)
                except (IndexError, ValueError):
                    continue
                if (not filetype) or (not filecount):
                    continue
                elif filetype not in ["i", "t", "v"]:
                    continue
                elif not filecount.isdecimal():
                    continue
                # Start counting from the highest count even if missing numbers.
                if filetype == "v":
                    video_count = max(video_count, count)
                elif filetype == "t":
                    timelapse_count = max(timelapse_count, count)
                else:
                    image_count = max(image_count, count)

        # Set the indexes to one greater than the last existing count.
        self.still_image_index = image_count + 1
        self.video_file_index = video_count + 1
        self.timelapse_index = timelapse_count + 1

    def generate_thumbnail(self, filetype, filepath):
        """Generates a thumbnail for a file of the given type and path.
        There are 3 types of files RaspiMJPEG differentiates between:
        Images ('i'), videos ('v') and timelapse sequences ('t'). The thumbnails
        are named slightly differently depending on which type it is.
        As with RaspiMJPEG, just copies the preview JPG file to use as thumbnail.
        """
        # Do not create unless included in thumb_gen setting.
        if filetype not in self.config["thumb_gen"]:
            return
        # Do not create if no preview image available.
        if not os.path.exists(self.config["preview_path"]):
            blank_thumbnail = np.zeros(
                (self.config["preview_size"][0], self.config["preview_size"][1], 3),
                np.uint8,
            )
            cv2.imwrite(self.config["preview_path"], blank_thumbnail)
        count = None
        if (filetype == "i"):
            count = self.still_image_index
            self.still_image_index += 1
        elif (filetype == "t"):
            count = self.timelapse_index
            self.timelapse_index += 1
        elif filetype == "v":
            count = self.video_file_index
            self.video_file_index += 1
        # Make actual thumbnail.
        thumbnail_path = filepath + "." + filetype + str(count) + ".th.jpg"
        shutil.copyfile(self.config["preview_path"], thumbnail_path)

    def reset_user_configs(self):
        """
        Helper method for set_camera_configuration for carrying out 'rs' commands.

        Makes a backup of the user config file as a .bak, then 'resets' the
        the user config file by overwriting its contents with that of the
        'default' configuration file (raspimjpeg in the case of RaspiMJPEG, but
        the config_path provided in this case of this program) and reloads
        all model settings from the default config file.

        Requires stopping and restarting the camera to execute.
        """
        # Make backup.
        backup_path = self.config["user_config"] + ".bak"
        shutil.copyfile(self.config["user_config"], backup_path)
        # Overwrite user config file contents with default provided configs.
        default_configs = [""]
        if self.default_config_path:
            cf_file = open(self.default_config_path, "r")
            default_configs = cf_file.readlines()
            cf_file.close()
        user_cf = open(self.config["user_config"], "w")
        for line in default_configs:
            user_cf.write(line)
        user_cf.close()
        self.read_config_file(self.default_config_path)

    def print_to_logfile(self, message):
        """
        Writes message to the specified log file. If log size is 0, does not
        write anything. No current functionality for limiting lines to log_size.
        RPi Cam Interface uses the same file to write its Scheduler logs to and
        differentiates between them by using [] for its own message timestamps while
        RaspiMJPEG uses {} for its message timestamps.
        """
        if self.config["log_size"] == 0:
            return

        timestring = "{" + datetime.now().strftime("%Y/%m/%d %H:%M:%S") + "}"
        timestring = timestring + "{Camera " + self.cam_index_str + "} "
        contents = timestring + message + "\n"
        log_fd = os.open(self.config["log_file"], os.O_RDWR | os.O_NONBLOCK, 0o777)
        log_file = os.fdopen(log_fd, "a")
        log_file.write(contents)
        log_file.close()

    def read_annotation_file(self):
        """
        Reads the user annotation from /dev/shm/mjpeg/user_annotate.txt if it exists.
        Returns the file content or an empty string if the file is not found.
        """
        annotation_file_path = self.config.get(
            "user_annotate", "/dev/shm/mjpeg/user_annotate.txt"
        )
        if os.path.exists(annotation_file_path):
            with open(annotation_file_path, "r") as file:
                return file.read().strip()
        return ""
