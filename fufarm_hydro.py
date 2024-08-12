"""Farm Urban Hydroponic System

Example configuration fufarm_hydro.yml file:
app:
  host: "localhost"
  port: 1883
  username: "hamqtt"
  password: "UbT4Rn3oY7!S9L"
  topic_prefix: "hydro"
  ec_prefix: "sensors/sensor/ec1"
  motor_pin: 0
  log_level: "DEBUG"
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
import os
import time

from typing import Callable

import paho.mqtt.client as mqtt

from util import (
    ID_CALIBRATE,
    ID_CONTROL,
    ID_DOSE_COUNT,
    ID_EC,
    ID_LAST_DOSE_TIME,
    ID_PARAMETERS,
    ID_STATE,
    ID_TOTAL_DOSE_TIME,
    AppState,
    AppConfig,
    create_on_connect,
    create_on_message,
    setup_mqtt_topics,
    process_config,
)


class Pump:
    """Mock class for running pump"""

    def __init__(self, pin):
        # pylint: disable=import-outside-toplevel,import-error
        self.mock = False
        try:
            import board
            import pwmio
            from adafruit_motor import servo
        except ImportError as e:
            _LOG.error("Error importing modules: %s", e)
            self.mock = True

        if not self.mock:
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
        if not self.mock:
            self.my_servo.throttle = 1.0
        time.sleep(dose_duration)
        if not self.mock:
            self.my_servo.throttle = 0.0
        return


def setup_mqtt(on_message: Callable, on_connect: Callable, app_config: AppConfig):
    """Setup the MQTT client and subscribe to topics."""
    # client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client = mqtt.Client()
    # host = "homeassistant.local"
    host = app_config.host
    port = app_config.port
    username = app_config.username
    password = app_config.password
    client.username_pw_set(username, password)
    client.connect(host, port=port)
    client.on_message = on_message
    client.on_connect = on_connect
    return client


def control_ec(
    state: AppState, pump: Pump, client: mqtt.Client, topics: dict[str, str]
):
    """Control the EC level"""
    if state.current_ec < state.target_ec:
        if time.time() - state.last_dose_time > state.equilibration_time:
            pump.run(state.dose_duration)
            state.last_dose_time = time.time()
            state.dose_count += 1
            state.total_dose_time += state.dose_duration
            status_json = state.status_json()
            _LOG.debug("Publishing state: %s", status_json)
            client.publish(topics[ID_STATE], status_json, qos=1, retain=True)
    return


def calibrate_ec():
    """Calibrate the EC sensor"""
    _LOG.info("Calibrating EC sensor")
    return


CONFIG_FILE = "fufarm_hydro.yml"
current_state = AppState()
app_config = AppConfig()
if os.path.isfile(CONFIG_FILE):
    app_config, current_state = process_config(CONFIG_FILE)

mqtt_topics = setup_mqtt_topics(app_config)

LOOP_DELAY = 3

logging.basicConfig(
    level=app_config.log_level,
    format="%(asctime)s rpi: %(message)s",
)
_LOG = logging.getLogger()


on_mqtt_message = create_on_message(current_state, mqtt_topics)
on_mqtt_connect = create_on_connect(
    [ID_CONTROL, ID_CALIBRATE, ID_EC, ID_PARAMETERS], mqtt_topics
)
mqtt_client = setup_mqtt(on_mqtt_message, on_mqtt_connect, app_config)
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
        control_ec(current_state, ec_pump, mqtt_client, mqtt_topics)

    time.sleep(LOOP_DELAY)
