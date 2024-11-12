<p align="center"><img src="https://github.com/user-attachments/assets/68c603cb-b79c-474a-aca6-e18a6acbb23c" height="90px" alt="RasPyCam Logo"></p>

<h1>Table of Contents</h1>

- [Overview](#overview)
- [Main Features](#main-features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
  - [Camera Control](#camera-control)
  - [Image and Video Capture](#image-and-video-capture)
  - [Motion Detection](#motion-detection)
  - [Camera Settings](#camera-settings)
  - [Configuration and Status](#configuration-and-status)
  - [Filename Creation](#filename-creation)
  - [Stopping the Program](#stopping-the-program)
- [Contributing](#contributing)
  - [Issues](#issues)
  - [Code Changes](#code-changes)
  - [Testing Changes](#testing-changes)
- [Acknowledgements](#acknowledgements)

<h1>Overview</h1>

RasPyCam is a python-based multi-stream camera system for the Raspberry Pi. This application has been designed as a replacement for the [RasPiCam](https://github.com/silvanmelchior/userland/tree/master/host_applications/linux/apps/raspicam) application developed by [Silvan Melchior](https://github.com/silvanmelchior), [Robert Tidey](https://github.com/roberttidey) and [others](https://github.com/silvanmelchior/RPi_Cam_Web_Interface/graphs/contributors) which is no longer maintained and has compatibility issues with the latest versions of the Raspberry Pi.

There are two ways of using RasPyCam:

1. **As a standalone program**: The program can be run on a Raspberry Pi with a camera module connected to it. The program will respond to manual command calls and perform the necessary actions. This method will use the source code provided in this repository.
2. **As a backend service**: The program can be run on a Raspberry Pi with a camera module connected to it alongside the [RPi Cam Web Interface](https://github.com/silvanmelchior/RPi_Cam_Web_Interface) system. The program will respond to the commands sent by the frontend and perform the necessary actions. This method will use the executable file created from the source code provided in this repository. As of version 1, the executable file is shipped with the [RPi Cam Web Interface](https://github.com/silvanmelchior/RPi_Cam_Web_Interface) system. Future updates to this repository will update the executable file in the frontend system.

<h1>Main Features</h1>

- **Preview**: Retrieve the camera feed in real time.
- **Image Capture**: Capture images from the connected camera.
- **Video Recording**: Record videos from the connected camera.
- **Motion Detection**: Detect motion in the camera feed.
- **Multi-Stream Support**: Stream multiple camera feeds simultaneously from the connected camera.
- **Web Interface Support**: Interact with the program using the [RPi Cam Web Interface](https://github.com/silvanmelchior/RPi_Cam_Web_Interface) system.

<h1>Requirements</h1>

Depending on how you run the program, you may need to install some dependencies, including [PiCamera 2](https://pypi.org/project/picamera2/0.2.2/), [OpenCV](https://pypi.org/project/opencv-python/), and [Pillow](https://pypi.org/project/pillow/).

If you would like to run the source code, you can install these libraries using the following commands:

```bash
pip install picamera2 opencv-python Pillow
```

<h1>Installation</h1>

1. Clone the repository to your Raspberry Pi:

```bash
git clone https://github.com/windermere-technology/raspycam.git
```

2. Run the installation script to install the program and its dependencies:

> [!NOTE]
> Depending on your Pi's configuration, you may need to run the program with `sudo` privileges. This is because the program requires read/write access to the tmp and var directories which are restricted to root access.

```bash
sudo ./install.sh
```

You will be prompted if you want the frontend ([RPi Cam Web Interface](https://github.com/silvanmelchior/RPi_Cam_Web_Interface)) to be install alongside the program. Select `y` if you want to install the frontend, otherwise select `n`.

After the install script finished, you can run the program standalone by running the following command, or it will run automatically with the frontend:

```bash
raspimjpeg [--config /path/to/config1 /path/to/config2 ...]
```

`path/to/config` is the path to the configuration file you want to use. If you don't specify a configuration file, the program will use the default configuration file provided in the repository. Provide 2 config will apply the settings to 2 cameras.

<h1>Usage</h1>

RasPyCam is a continuously running program that observes the commands sent to the named pipe (by default this is `/var/FIFO`).

To send commands to the program, you can use the following commands:

```bash
echo '{command} {parameter}' > /var/FIFO
```

> [!NOTE]
> While the front end is running, the RasPyCam program will be running under www-data user. This means that the FIFO file will be located in `/var/www/html/FIFO` instead of `/var/FIFO`. And you will need to send commands as www-data user.

```bash
sudo su -c "echo '{command} {parameter}' >> /var/www/html/FIFO" www-data
```

> [!NOTE]
> Angled brackets refer to \<optional parameters\>.

> [!NOTE]
> Square brackets are used to send commands to multiple cameras. Command and sets of parameters are separated by commas. Forward slashes escape commas. Leading and trailing whitespaces are not stripped from parameters. Not enclosing parameters within brackets applies the parameters to all bracketed commands.

> Example 1: `[dp,dp] [0,1]` = Switches off preview for Camera 0, switches on preview for Camera 1.

> Example 2: `[im,an] [,Look/, an annotation!]` = Takes a still image with Camera 0, sets the annotation for Camera 1 to "Look, an annotation!".

> Example 3: `[,im] ` = Camera 0 is not sent any command. Takes an image with Camera 1.

> Example 4: `[ca,ca] 1` = Starts recording on both Camera 0 and Camera 1.

> [!IMPORTANT]
> The commands `ix+ix` and `im+im` can only be used within square brackets, even if only sent to 1 camera.

Currently the program supports the following commands:

<h2>Camera Control</h2>

| Command | Parameter | Description |
| --- | --- | --- |
| `ru` | 1/0 | Starts (1) or stops (0) the camera. The program continues to run while the camera is stopped, but the only accepted command will be `ru 1` to restart. |
| `cn` | {number} | Changes the main camera to the specified number. The number corresponds to the slot index of Picam2's `all_cameras()` function. |
| `fl` | 0/1/2/3 | Sets horizontal and vertical flip. The parameters are: no flip (0), horizontal flip (1), vertical flip (2), and both horizontal and vertical flip (3). The default is 0. |
| `dp` | 1/0 | Enables (1) or disables (0) the camera preview. If multiple cameras have previews enabled and share the same image height, they will be stitched together horizontally. |

<h2>Image and Video Capture</h2>

| Command | Parameter | Description |
| --- | --- | --- |
| `ca` | 1/0 {duration} | Starts (1) or stops (0) video recording. Optionally, you can specify a duration in seconds. |
| `im` | | Takes a still image at current sensor resolution and image size. |
| `[im+im]` | \<v/h\> | Takes a stitched image from all available cameras at their current resolutions and image sizes. You can either vertically (v) stitch or horizontally (h) stitch the feeds. If no axis is specified, stitching will be done horizontally. |
| `ix` | | Captures an image at the maximum possible sensor resolution and image size, by switching camera configurations and then switching back. Will restart cameras. |
| `[ix+ix]` | \<v/h\> | Captures a stitched image from all available cameras at the maximum resolution, by switching their configurations and then switching back. You can either vertically (v) stitch or horizontally (h) stitch the feeds. If no axis is specified, stitching will be done horizontally. Will restart cameras. |

<h2>Motion Detection</h2>

| Command | Parameter | Description |
| --- | --- | --- |
| `md` | 1/0 | Starts (1) or stops (0) motion detection. |
| `mx` | 0/2 | Switches the motion detection mode between internal (0) detection and monitor mode (2). |
| `mt` | {value} | Sets motion detection parameters for threshold. |
| `ms` | {value} | Sets motion detection parameters for number of frames to delay just after turning on motion detection. |
| `mb` | {value} | Sets motion detection parameters for number of frames of detected motion needed to register start of motion. |
| `me` | {value} | Sets motion detection parameters for number of frames without motion needed to register end of motion. |

<h2>Camera Settings</h2>

| Command | Parameter | Description |
| --- | --- | --- |
| `bi` | {bitrate} | Sets the video bitrate (must be between 0 and 25,000,000). |
| `sh` | {value} | Sets the sharpness of the camera. |
| `co` | {value} | Sets the contrast of the camera. |
| `br` | {value} | Sets the brightness of the camera. |
| `sa` | {value} | Sets the saturation of the camera. |
| `wb` | {value} | Sets the white balance mode of the camera. |
| `ag` | {value} | Sets the analog (colour) gain of the camera. |
| `ss` | {value} | Sets the shutter speed (exposure time) of the camera. |
| `an` | {value} | Sets the annotation text on the camera feed. See [Filename Creation](#filename-creation) for more details |
| `ec` | {value} | Sets exposure compensation. |
| `is` | {value} | Sets the ISO level. |
| `qu` | {value} | Sets the JPEG image quality (1-100). |
| `pv` | {quality} {width} {divider} \<height\> | Adjusts preview settings. Height is optional, if not specified, will automatically set height based on width according to 16:9 aspect ratio. |
| `px` | {video width} {video height} {video fps} {encoder fps} {image width} {image height} | Adjusts video and image settings in bulk. Will restart cameras. |

<h2>Configuration and Status</h2>

| Command | Parameter | Description |
| --- | --- | --- |
| `rs` | | Resets the user configuration file as specified in the initially supplied config's `user_config` setting and reloads the camera instance’s settings from the initially supplied config file. Will restart cameras. |
| `sc` | | Recounts and updates the internal tally of image and video files in the output folders. |
| `cr` | {width height} | Changes the camera sensor resolution. Will restart cameras. |
| `cs` | i/v/i+v {width height} {width height} | Changes image (i), video (v), or both (i+v) stream sizes. Specifying the second set of width and height only needs to be done when using i+v. Will restart cameras. |
| `1s` | 0/1/2 | Switches to solo stream mode (1), optionally sets to the maximum sensor resolution if (2) is provided or switches off solo stream mode (0). Will restart cameras. |
| sy | {script} [args...] | Executes a user-defined macro script located in /var/www/html/macros/. {script} is the script file name (e.g., mktimelapse.sh). | 

If the program is initated without a specified configuration file, the program will utilise the following paths for inputs and outputs:
| Type | Path |
| --- | --- |
| Preview | /tmp/preview/cam*preview.jpg |
| Videos | /tmp/media/vi_cam%I*%v*%Y%M%D*%h%m%s.mp4 |
| Stills | /tmp/media/im*cam%I*%i*%Y%M%D*%h%m%s.jpg |
| Status File | /tmp/status_mjpeg.txt |

> Command names, parameters and paths have been sourced from the [RPi Cam Web Interface](https://github.com/silvanmelchior/RPi_Cam_Web_Interface) system to ensure compatibility. In addition to the existing naming scheme used to interpolate values into filenames, the code %I can be used to refer a camera's index number.

<h2>Filename Creation</h2>

Filenames can be created with standard text alongside the following naming scheme:

| Code | Description |
| --- | --- |
| %Y | Four-digit year (e.g., 2023) |
| %y | Two-digit year (e.g., 23) |
| %M | Month (01-12) |
| %D | Day of the month (01-31) |
| %h | Hour (00-23) |
| %m | Minute (00-59) |
| %s | Second (00-59) |
| %u | Milliseconds (000-999) |
| %i | Image index (increments with each image captured) |
| %v | Video index (increments with each video recorded) |
| %I | Camera index, indicating the camera number if multiple cameras are used |
| %a | Custom annotation text, provided by the user |
| %% | Literal % symbol in the filename |

> [!NOTE]
> The `%a` code will read the text from the `/dev/shm/mjpeg/user_annotate.txt` file by default. This file must be created by the user. You may change this default path in the configuration file by adjusting the `user_annotate` parameter.

<h2>Stopping the Program</h2>

To stop the program, you can either send SIGINT or SIGTERM signals to the program. This can be done by either pressing `Ctrl+C` in the terminal running the program or by using the `kill` command.

If you've launched the program using the source code, run the following command:

```bash
sudo kill -9 $(cat /opt/vc/bin/raspycam/raspy.pid)
```

Or if you've launched the program using the front-end, navigate to the front-end directory and run the following command, or simply press the stop button in the front-end:

```bash
sudo ./stop.sh
```

<h1>Contributing</h1>

Contributions to the RasPyCam project are welcome. If you would like to contribute to the project, please follow the steps below:

<h2>Issues</h2>

If you encounter any issues with the program, you can create a new issue on the [Issues](https://github.com/Windermere-Technology/RasPyCam/issues) page and use one of the provided templates to report the issue.

<h2>Code Changes</h2>

To make changes to the code, you can follow the steps below:

1. Fork the repository and clone it to your local machine
2. Make your changes, commit and push them to your forked repository
3. Create a pull request back to the main repository ([Windermere-Technology/RasPyCam](https://github.com/windermere-technology/raspycam))
4. Wait for the pull request to be reviewed and merged

<h2>Testing Changes</h2>

To test your changes and generage a coverage report, you can run the following commands on a Raspberry Pi with a camera module connected to it:

```bash
sudo apt update
sudo apt install libcap-dev python3-pytest libopencv-dev python3-pytest-cov -y
```

```bash
PYTHONPATH=./app pytest --import-mode=importlib --cov=app --cov-report=term --cov-report=html:coverage_html --cov-config=tests/.coveragerc
```

This command will run the testing suite and generate a coverage report. You can view this report by opening the `coverage_html/index.html` file in your browser. If you want to test a specific folder or file, just add the path to the end of the command.

<h1>Acknowledgements</h1>

The development of this project was inspired by the [RasPiCam](https://github.com/silvanmelchior/userland/tree/master/host_applications/linux/apps/raspicam) application developed by [Silvan Melchior](https://github.com/silvanmelchior), [Robert Tidey](https://github.com/roberttidey) and [others](https://github.com/silvanmelchior/RPi_Cam_Web_Interface/graphs/contributors).

Initially devleoped as part of a University project overseen by [Cian Byrne](https://github.com/wallarug), the development team consisted of:

- [Kyle Graham](https://github.com/kaihokori)
- [Harry Le (Lê Thành Nhân)](https://github.com/NhanDotJS)
- [Chen-Don Loi](https://github.com/Chen-Loi)
- [Qiuda (Richard) Song](https://github.com/RichardQiudaSong)
