"""Farm Urban Hydroponic System

Listen for messages to:
* Calibrate sensors
* Set dosing parameters
* Switch between monitor/control


Subscribe to MQTT broker - topics:
* farm/calibrate - which sensor to calibrate
* farm/parameters - set dosing parameters
* farm/control - switch between monitor/control

Key variables:
current_ec
target_ec
dose_duration
dose_interval
last_dose_time


Check aiomqtt for async MQTT client
"""

import time

dose_interval = 60.0

current_ec = 0.0
target_ec = 2.0
last_dose_time = time.time()

ec_pump = Pump(1)


def on_message(client, userdata, message):
    topic = message.topic
    payload = message.payload.decode("utf-8")
    if topic == "farm/calibrate":
        if payload == "ec":
            ec_sensor.calibrate()
    elif topic == "farm/parameters":
        dose_duration, dose_interval = payload.split(",")
    elif topic == "farm/control":
        if payload == "monitor":
            ec_pump.stop()

def read_ec():


def control_ec():
    current_ec = ec_sensor.read()
    if current_ec < target_ec:
        if time.time() - last_dose_time > dose_interval:
            last_dose_time = time.time()
            ec_pump.run(dose_interval)
