#!/usr/bin/env bash

REQUIRED_PYTHON_VERSION="3.10"
PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')

if [[ $(printf '%s\n' "$REQUIRED_PYTHON_VERSION" "$PYTHON_VERSION" | sort -V | head -n1) != "$REQUIRED_PYTHON_VERSION" ]]; then
    echo "Python $REQUIRED_PYTHON_VERSION or above is required for this script."
    echo "Your current Python version is $PYTHON_VERSION."
    echo "Please update Python by following these steps:"
    echo "1. Update the package list: sudo apt update"
    echo "2. Install the latest Python version: sudo apt install python3"
    echo "3. Verify the version: python3 --version"
    echo "Exiting installation. Please re-run the script after updating Python."
    exit 1
fi

fn_install_rpi_web()
{   
    echo "RPI-Cam-Web-Interface installation"
    git clone https://github.com/consiliumsolutions/RPi_Cam_Web_Interface
    sleep 1
    sudo apt install python3-opencv
    sudo mkdir -p RPi_Cam_Web_Interface/raspycam
    sudo cp etc/rpi-cam-web-interface/* RPi_Cam_Web_Interface/
    sudo cp -rf app/* RPi_Cam_Web_Interface/raspycam/
    sudo cp etc/raspycam RPi_Cam_Web_Interface/raspycam/raspycam
    sudo ./RPi_Cam_Web_Interface/install.sh 
}

fn_alone_install()
{
    echo "Alone installation"
    sudo apt install python3-opencv
    sudo cp -rf app/* /opt/vc/bin/raspycam/
    sudo cp etc/raspycam /opt/vc/bin/raspycam/raspycam
    sudo chmod -R 755 /opt/vc/bin/raspycam
    sudo touch /opt/vc/bin/raspycam/raspy.pid
    sudo touch /opt/vc/bin/raspycam/raspy.log
    sudo chmod 777 /opt/vc/bin/raspycam/raspy.pid
    sudo chmod 777 /opt/vc/bin/raspycam/raspy.log
    sudo cp etc/default.conf /etc/raspimjpeg
    if [ -e /usr/bin/raspimjpeg ]; then
        sudo rm -f /usr/bin/raspimjpeg
    fi
    sudo ln -s /opt/vc/bin/raspycam/raspycam /usr/bin/raspimjpeg
    
}

while true; do
    read -p "Do you wish to install RPI-Cam-Web-Interface as well? (Y/N) " yn
    case $yn in
        [Yy]* ) fn_install_rpi_web; break;;
        [Nn]* ) fn_alone_install; break;;
        * ) echo "Invalid answer, cancel installation"; exit;;
    esac
done
