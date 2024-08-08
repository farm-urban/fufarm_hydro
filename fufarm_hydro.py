"""Farm Urban Hydroponic System

Example configuration fufarm_hydro.yml file:
app:
  motor_pin: 0
  log_level: 'DEBUG'
  topic_prefix: 'hydro'
  ec_prefix: 'sensors/sensor/ec1'
state:
  control: False
  should_calibrate: False
  equilibration_time: 3
  current_ec: 10.0
  target_ec: 1.8
  last_dose_time: 0
  dose_duration: 5
~                   

Notes:
https://learn.adafruit.com/circuitpython-on-raspberrypi-linux/installing-circuitpython-on-raspberry-pi

Could look at aiomqtt for async MQTT client
"""

import logging
import json
import os
import time

from dataclasses import dataclass
from typing import Callable

import paho.mqtt.client as mqtt
import yaml


class Pump:
    """Mock class for running pump"""

    def __init__(self, pin):
        # pylint: disable=import-outside-toplevel,import-error
        import board
        import pwmio
        from adafruit_motor import servo

        pid = f"D{pin:d}"
        if not hasattr(board, pid):
            raise AttributeError(f"Could not find pin {pin} on board")
        pwm = pwmio.PWMOut(getattr(board, pid), frequency=50)
        self.my_servo = servo.ContinuousServo(pwm)

    def run(self, dose_duration):
        """Dose for a given duration

        1.0 is full speed forward
        0.0 is stopped
        -1.0 is full speed reverse
        """
        _LOG.info("Dosing for %d seconds", dose_duration)
        self.my_servo.throttle = 1.0
        time.sleep(dose_duration)
        self.my_servo.throttle = 0.0
        return


@dataclass
class State:
    """Tracks the current state of the autodoser."""

    control: bool = False
    should_calibrate: bool = False
    equilibration_time: int = 3
    current_ec: float = 10.0  # Set to a high value to prevent dosing before reading EC
    target_ec: float = 1.8
    last_dose_time: float = time.time() - equilibration_time
    dose_duration: int = 5

    def __repr__(self):
        return "<\n%s\n>" % str(
            "\n ".join("%s : %s" % (k, repr(v)) for (k, v) in self.__dict__.items())
        )


@dataclass
class AppConfig:
    """Configures the Application."""

    motor_pin: int = 0
    log_level: str = "INFO"
    topic_prefix: str = "hydro"
    ec_prefix: str = "sensors/sensor/ec1"

    def __repr__(self):
        return "<\n%s\n>" % str(
            "\n ".join("%s : %s" % (k, repr(v)) for (k, v) in self.__dict__.items())
        )


def process_config(
    file_path,
):
    """Process the configuration file."""
    with open(file_path, "r", encoding="utf-8") as f:
        yamls = yaml.safe_load(f)
        if "app" in yamls:
            _app_config = AppConfig(**yamls["app"])
        if "state" in yamls:
            _current_state = State(**yamls["state"])

    if not hasattr(logging, app_config.log_level):
        raise AttributeError(f"Unknown log_level: {_app_config.APP.log_level}")

    return _app_config, _current_state


def setup_mqtt(on_message: Callable):
    """Setup the MQTT client and subscribe to topics."""
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    # host = "homeassistant.local"
    host = "localhost"
    port = 1883
    username = "hamqtt"
    password = "UbT4Rn3oY7!S9L"
    client.username_pw_set(username, password)
    client.connect(host, port=port)
    client.on_message = on_message
    client.on_connect = on_connect
    return client


def create_on_message(state: State):
    """Create a callback to handle incoming MQTT messages."""

    def on_message(_client, _userdata, message):
        topic = message.topic
        payload = message.payload.decode("utf-8")
        _LOG.debug("Received message: %s %s", topic, payload)
        if topic == TOPICS[CALIBRATE]:
            if payload == "ec":
                state.should_calibrate = True
            else:
                _LOG.warning("Invalid payload for calibrate topic: %s", payload)
        elif topic == TOPICS[CONTROL]:
            if payload == "0":
                state.control = False
            elif payload == "1":
                state.control = True
            else:
                _LOG.warning("Invalid payload for control topic: %s", payload)
        elif topic == TOPICS[EC]:
            try:
                state.current_ec = float(payload)
            except ValueError as e:
                _LOG.warning("Error getting EC: %s - %s", payload, e)
                state.current_ec = -1.0
        elif topic == TOPICS[PARAMETERS]:
            process_parameters(payload, state)

    # End of on_message

    return on_message


def process_parameters(payload: str, state: State):
    """Process the parameters from the MQTT message."""
    _LOG.debug("Processing parameter update: %s", payload)
    try:
        data = json.loads(payload)
    except json.decoder.JSONDecodeError as e:
        _LOG.warning(
            "Error decoding PARAMETERS data to JSON: %s\nMessage was: %s",
            e.msg,
            e.doc,
        )
    if "dose_duration" in data:
        state.dose_duration = data["dose_duration"]
    if "equilibration_time" in data:
        state.equilibration_time = data["equilibration_time"]
    if "target_ec" in data:
        state.target_ec = data["target_ec"]


def on_connect(client, _userdata, _flags, _reason_code, _properties):
    """Subscribe to topics on connect."""
    retcodes = []
    for topic in TOPICS.values():
        retcodes.append(client.subscribe(topic))
    if all([retcode[0] == mqtt.MQTT_ERR_SUCCESS for retcode in retcodes]):
        _LOG.debug("Subscribed to topics: %s", [v for v in TOPICS.values()])
    else:
        _LOG.warning("Error subscribing to topics: %s", retcodes)


def control_ec(state: State, pump: Pump):
    """Control the EC level"""
    if state.current_ec < state.target_ec:
        if time.time() - state.last_dose_time > state.equilibration_time:
            _LOG.debug("Dosing for %d seconds", state.dose_duration)
            pump.run(state.dose_duration)
            state.last_dose_time = time.time()
    return


def calibrate_ec():
    """Calibrate the EC sensor"""
    _LOG.info("Calibrating EC sensor")
    return


CONFIG_FILE = "fufarm_hydro.yml"
current_state = State()
app_config = AppConfig()
if os.path.isfile(CONFIG_FILE):
    app_config, current_state = process_config(CONFIG_FILE)

LOOP_DELAY = 3
SEPARATOR = "/"
CALIBRATE = "calibrate"
CONTROL = "control"
EC = "ec"
PARAMETERS = "parameters"
TOPICS = {
    CONTROL: SEPARATOR.join([app_config.topic_prefix, CONTROL]),
    CALIBRATE: SEPARATOR.join([app_config.topic_prefix, CALIBRATE]),
    EC: app_config.ec_prefix,
    PARAMETERS: SEPARATOR.join([app_config.topic_prefix, PARAMETERS]),
}


logging.basicConfig(
    level=app_config.log_level,
    format="%(asctime)s rpi: %(message)s",
)
_LOG = logging.getLogger()


on_mqtt_message = create_on_message(current_state)
mqtt_client = setup_mqtt(on_mqtt_message)
ec_pump = Pump(app_config.motor_pin)
mqtt_client.loop_start()

last_dose_time = time.time()
while True:
    while not mqtt_client.is_connected():
        _LOG.warning("mqtt_client not connected")
        mqtt_client.reconnect()
        time.sleep(2)
    _LOG.info("%s", current_state)

    if current_state.should_calibrate:
        calibrate_ec()

    if current_state.control:
        control_ec(current_state, ec_pump)

    time.sleep(LOOP_DELAY)
