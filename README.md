# fufarm_hydro
Code for the Hydroponics Control system within Home Assistant

Setup virtual enviroment with:
python3 -m venv venv


# Enable i2c
sudo raspi-config nonint do_i2c 0

Install Adafruit Blinka
https://learn.adafruit.com/circuitpython-on-raspberrypi-linux/installing-circuitpython-on-raspberry-pi

isudo apt-get install -y i2c-tools libgpiod-dev python3-libgpiod
#pip3 install --upgrade RPi.GPIO
pip3 install rpi-lgpio
pip3 install --upgrade adafruit-blinka


Then
pip3 install adafruit-circuitpython-motor
