# fufarm_hydro
Code for the Hydroponics Control system within Home Assistant

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
