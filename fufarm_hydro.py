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

import logging
import json
import time
import paho.mqtt.client as mqtt

logging.basicConfig(
    level="INFO",
    format=f"%(asctime)s rpi: %(message)s",
)
logger = logging.getLogger()


dose_interval = 60.0

current_ec = 0.0
target_ec = 2.0
last_dose_time = time.time()

ec_pump = Pump(1)


# def read_ec():


def control_ec():
    current_ec = ec_sensor.read()
    if current_ec < target_ec:
        if time.time() - last_dose_time > dose_interval:
            last_dose_time = time.time()
            ec_pump.run(dose_interval)
    return last_dose_time


def toggle_control():
    """Check for message to toggle control"""
    return


def should_run_clibration():
    """Check for message to calibrate"""
    return


def on_message(client, userdata, message):
    topic = message.topic
    payload = message.payload.decode("utf-8")
    if topic == "farm/calibrate":
        if payload == "ec":
            ec_sensor.calibrate()
    elif topic == "farm/parameters":
        try:
            data = json.loads(payload)
        except json.decoder.JSONDecodeError as e:
            logger.warning(
                "Error decoding MQTT data to JSON: %s\nMessage was: %s", e.msg, e.doc
            )
        dose_duration = data.get("dose_duration", 1)
        dose_interval = data.get("dose_interval", 60)
    elif topic == "farm/control":
        if payload == 0:
            ec_pump.stop()


def setup_mqtt():
    client = mqtt.Client()
    client.username_pw_set(CONFIG.MQTT.username, CONFIG.MQTT.password)
    ret = client.connect(CONFIG.MQTT.host, port=CONFIG.MQTT.port)
    logger.debug(f"MQTT client connect return code: {ret}")

    # Add different plugs
    for topic in ["farm/calibrate", "farm/parameters", "farm/control"]:
        client.subscribe(topic)
    client.on_message = on_message

    return client


client = setup_mqtt()
client.loop_start()

control = True
while True:
    # Below seems to raise an exception - not sure why
    if not client.is_connected():
        logger.error("mqtt_client not connected")
        client.reconnect()

    if should_run_clibration():
        ec_sensor.calibrate()

    if toggle_control():
        control = not control

    if control:
        last_dose_time = control_ec(last_dose_time)

    time.sleep(1)
