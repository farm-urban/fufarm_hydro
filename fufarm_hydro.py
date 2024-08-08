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

from dataclasses import dataclass

import logging
import json
import sys
import time
from typing import Callable

import paho.mqtt.client as mqtt


logging.basicConfig(
    level="DEBUG",
    format=f"%(asctime)s rpi: %(message)s",
)
_LOG = logging.getLogger()

SEPARATOR = "/"
CALIBRATE = "calibrate"
CONTROL = "control"
PARAMETERS = "parameters"
TOPIC_PREFIX = "hydro"
TOPICS = {
    CONTROL: SEPARATOR.join([TOPIC_PREFIX, CONTROL]),
    CALIBRATE: SEPARATOR.join([TOPIC_PREFIX, CALIBRATE]),
    PARAMETERS: SEPARATOR.join([TOPIC_PREFIX, PARAMETERS]),
}


class Pump:
    """Mock class for running pump"""

    def __init__(self, pin):
        self.pin = pin

    def run(self, dose_duration):
        """Dose for a given duration"""
        _LOG.info("Dosing for %d seconds", dose_duration)
        return


@dataclass
class State:
    """Tracks the current state of the app."""

    control: bool = True
    should_calibrate: bool = False
    equilibration_time: int = 60
    current_ec: float = 10.0
    target_ec: float = 1.8
    last_dose_time: float = time.time()
    dose_duration: int = 5

    def __repr__(self):
        return "<\n%s\n>" % str(
            "\n ".join("%s : %s" % (k, repr(v)) for (k, v) in self.__dict__.items())
        )


def control_ec(state: State, pump: Pump):
    """Control the EC level"""
    if state.current_ec < state.target_ec:
        if time.time() - state.last_dose_time > state.equilibration_time:
            # _LOG.info("Dosing for %d seconds", dose_duration)
            pump.run(state.dose_duration)
            state.last_dose_time = time.time()
    return


def get_current_ec():
    """Get the current EC level"""
    return 0.0


def create_on_message(state: State):
    """Create a callback to handle incoming MQTT messages."""

    def on_message(_client, _userdata, message):
        topic = message.topic
        payload = message.payload.decode("utf-8")
        _LOG.debug("Received message: %s %s", topic, payload)
        if topic == TOPICS[CALIBRATE]:
            if payload == "ec":
                state.should_calibrate = True
        elif topic == TOPICS[CONTROL]:
            if payload == 0:
                state.control = False
            elif payload == 1:
                state.control = True
            else:
                _LOG.warning("Invalid payload for control topic: %s", payload)
        elif topic == TOPICS[PARAMETERS]:
            try:
                data = json.loads(payload)
            except json.decoder.JSONDecodeError as e:
                _LOG.warning(
                    "Error decoding PARAMETERS data to JSON: %s\nMessage was: %s",
                    e.msg,
                    e.doc,
                )
            if "equilibration_time" in data:
                state.equilibration_time = data["equilibration_time"]
            if "target_ec" in data:
                state.target_ec = data["target_ec"]
        return

    return on_message


def setup_mqtt(on_message: Callable):
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    host = "homeassistant.local"
    port = 1883
    username = "hamqtt"
    password = "UbT4Rn3oY7!S9L"
    client.username_pw_set(username, password)
    ret = client.connect(host, port=port)
    _LOG.debug("MQTT client connect return code: %d", ret)
    # Add different plugs
    for topic in TOPICS.values():
        client.subscribe(topic)
    client.on_message = on_message
    return client


current_state = State()
on_mqtt_message = create_on_message(current_state)
mqtt_client = setup_mqtt(on_mqtt_message)
ec_pump = Pump(1)

mqtt_client.loop_start()
last_dose_time = time.time()
while True:
    while not mqtt_client.is_connected():
        _LOG.warning("mqtt_client not connected")
        ret = mqtt_client.reconnect()
        _LOG.debug("MQTT client reconnect return code: %d", ret)
        time.sleep(2)
    _LOG.info("mqtt_client connected: %s", mqtt_client.is_connected())
    _LOG.info("state connected: %s", current_state)

    current_state.current_ec = get_current_ec()
    if current_state.should_calibrate:
        _LOG.info("Calibrating EC sensor")

    if current_state.control:
        _LOG.info("Calling control_ec")
        control_ec(current_state, ec_pump)

    time.sleep(3)
