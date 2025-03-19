# fufarm_hydro

A standalone Hydroponics Control system.

This provides a web app that can be used to monitor and control the nutrient and acid dosing of a hydroponics system.

The app is designed to work in two ways:

- locally, where it is installed on a Raspberry Pi and the probes and peristaltic pumps are attached directly to the Raspberry Pi (using a [DFRobot IO Expansion HAT for Raspberry Pi](https://wiki.dfrobot.com/IO%20Expansion%20HAT%20for%20Raspberry%20Pi%20%20SKU%3A%20%20DFR0566)) and controlled via [MQTT-IO](https://github.com/flyte/mqtt-io).
- remotely, where the sensors and control are on a separate system (such as an [Arduino](https://github.com/farm-urban/fufarm_arduino_sensors)) and control is facilitated via MQTT [only partially implemented].

The app is started by running the `./run_webapp.sh` script in the main directory and can be accessed at [http://localhost:5000](http://localhost:5000)

## Architecture

The application is based on [Flask](https://github.com/pallets/flask) and architected with the following classes:

- AppState - holds the various control variables which can be read/set by different processes.
- HydroController `hydrocontrol_ui/hydrocontrol/controller.py` - loops and checks for updates of the AppState and invokes actions based on state changes.
- Flask App - web app `hydrocontrol_ui/views.py` the UI for the controller. It runs in the same process as the HydroController, and shares it's AppState, so any changes made by the UI are propagated to the HydroController.
- ec_calibrator `hydrocontrol_ui/hydrocontrol/ec_calibrator.py` functions to run calibration locally with MQTT-IO controlled peristaltic pump.

## Installation

Install Adafruit Blinka
https://learn.adafruit.com/circuitpython-on-raspberrypi-linux/installing-circuitpython-on-raspberry-pi

# Enable i2c

sudo raspi-config nonint do_i2c 0

# Install required system-wide packages

sudo apt-get install -y i2c-tools libgpiod-dev python3-libgpiod

# Set up the virtual python environment a(nd install all the requried packages if necessary)

#pip3 install rpi-lgpio
#pip3 install --upgrade adafruit-blinka
#pip3 install adafruit-circuitpython-motor

source ./venv_activate.sh
