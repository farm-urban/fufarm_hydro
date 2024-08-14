"""Farm Urban Hydroponic System~                   

Notes:
https://learn.adafruit.com/circuitpython-on-raspberrypi-linux/installing-circuitpython-on-raspberry-pi

Could look at aiomqtt for async MQTT client
"""

import logging
import os
import time

from typing import Callable

import paho.mqtt.client as mqtt

from mqtt_util import (
    ID_CALIBRATE,
    ID_CONTROL,
    ID_EC,
    ID_MANUAL_DOSE,
    ID_PARAMETERS,
    ID_STATE,
    create_on_connect,
    create_on_message,
    setup_mqtt_topics,
)
from state_classes import AppConfig, AppState, process_config


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


class HydroController:
    """Hydroponic controller"""

    def __init__(self, app_config: AppConfig, current_state: AppState):

        self.current_state = current_state
        self.app_config = app_config

        self.mqtt_topics = setup_mqtt_topics(app_config)
        on_mqtt_message = create_on_message(current_state, self.mqtt_topics)
        on_mqtt_connect = create_on_connect(
            [ID_CONTROL, ID_CALIBRATE, ID_EC, ID_MANUAL_DOSE, ID_PARAMETERS],
            self.mqtt_topics,
        )
        self.mqtt_client = self.setup_mqtt(on_mqtt_message, on_mqtt_connect, app_config)
        self.ec_pump = Pump(app_config.motor_pin)

        self.loop_delay = 3

    @staticmethod
    def setup_mqtt(on_message: Callable, on_connect: Callable, app_config: AppConfig):
        """Setup the MQTT client and subscribe to topics."""
        # client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        client = mqtt.Client()
        host = app_config.host
        port = app_config.port
        username = app_config.username
        password = app_config.password
        client.username_pw_set(username, password)
        client.connect(host, port=port)
        client.on_message = on_message
        client.on_connect = on_connect
        return client

    def control_ec(self):
        """Control the EC level"""
        if self.current_state.current_ec < self.current_state.target_ec:
            if (
                time.time() - self.current_state.last_dose_time
                > self.current_state.equilibration_time
            ):
                self.ec_pump.run(self.current_state.dose_duration)
                self.current_state.last_dose_time = time.time()
                self.current_state.dose_count += 1
                self.current_state.total_dose_time += self.current_state.dose_duration
                status_json = self.current_state.status_json()
                _LOG.debug("Publishing state: %s", status_json)
                self.mqtt_client.publish(
                    self.mqtt_topics[ID_STATE], status_json, qos=1, retain=True
                )
        return

    def calibrate_ec(self):
        """Calibrate the EC sensor"""
        _LOG.info("Calibrating EC sensor")
        time.sleep(5)
        self.current_state.should_calibrate_ec = False
        return

    def manual_dose(self):
        """Dose for a given duration"""
        self.ec_pump.run(self.current_state.manual_dose_duration)
        self.current_state.last_dose_time = time.time()
        self.current_state.dose_count += 1
        self.current_state.total_dose_time += self.current_state.manual_dose_duration
        status_json = self.current_state.status_json()
        _LOG.debug("Publishing state following manual dose: %s", status_json)
        self.mqtt_client.publish(
            self.mqtt_topics[ID_STATE], status_json, qos=1, retain=True
        )
        self.current_state.manual_dose = False
        return

    def run(self):
        """Run the hydro controller"""
        self.mqtt_client.loop_start()
        while True:
            while not self.mqtt_client.is_connected():
                _LOG.warning("mqtt_client not connected")
                self.mqtt_client.reconnect()
                time.sleep(2)
            # _LOG.debug("%s", self.current_state)

            if self.current_state.should_calibrate_ec:
                self.calibrate_ec()

            if self.current_state.manual_dose:
                self.manual_dose()

            if self.current_state.control:
                self.control_ec()

            time.sleep(self.loop_delay)


CONFIG_FILE = "fufarm_hydro.yml"
APP_CONFIG = AppConfig()
CURRENT_STATE = AppState()
if os.path.isfile(CONFIG_FILE):
    APP_CONFIG, CURRENT_STATE = process_config(CONFIG_FILE)

logging.basicConfig(
    level=APP_CONFIG.log_level,
    format="%(asctime)s rpi: %(message)s",
)
_LOG = logging.getLogger()

if __name__ == "__main__":
    controller = HydroController(APP_CONFIG, CURRENT_STATE)
    controller.run()
