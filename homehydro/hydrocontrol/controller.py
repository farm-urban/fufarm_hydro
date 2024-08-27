"""Farm Urban Hydroponics Control System               

"""

import logging
import os
import socket
import time

from typing import Callable

import paho.mqtt.client as mqtt

from homehydro.hydrocontrol.state_classes import (
    AppConfig,
    AppState,
    CalibrationStatus,
    process_config,
)
from homehydro.hydrocontrol.ec_calibrator import CalibrationData, run_calibration


ID_EC = "ec"
_LOG = logging.getLogger()


class Pump:
    """Class for running peristaltic dosing pump"""

    def __init__(self, channel: int):
        # pylint: disable=import-outside-toplevel,import-error
        self.mock = False
        try:
            from mqtt_io.modules.sensor.drivers.dfr0566_driver import (
                DFRobotExpansionBoardIIC,
                DFRobotExpansionBoardServo,
            )
        except ImportError as e:
            _LOG.error("Error importing pump driver modules: %s", e)
            self.mock = True

        if not self.mock:
            board = DFRobotExpansionBoardIIC(
                1, 0x10
            )  # Select i2c bus 1, set address to 0x10
            self.servo = DFRobotExpansionBoardServo(board)
            self.channel = channel
            board.setup()
            self.servo.begin()

    def run(self, dose_duration):
        """Dose for a given duration
        0 is full speed forward
        90 is stopped
        180 is full speed reverse
        """
        _LOG.info("Dosing for %d seconds", dose_duration)
        if not self.mock:
            self.servo.move(self.channel, 0)
        time.sleep(dose_duration)
        if not self.mock:
            self.servo.move(self.channel, 90)
        return


class HydroController:
    """Hydroponic controller"""

    def __init__(
        self, app_config: AppConfig, current_state: AppState, mqttio_config_file: str
    ):

        self.current_state = current_state
        self.app_config = app_config
        self.mqttio_config_file = mqttio_config_file

        self.mqtt_client = self.setup_mqtt()
        self.ec_pump = Pump(app_config.motor_channel)

        self.loop_delay = 3

    def setup_mqtt(self):
        """Setup the MQTT client and subscribe to topics."""
        # client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        client = mqtt.Client()
        host = self.app_config.mqtt_host
        port = self.app_config.mqtt_port
        username = self.app_config.mqtt_username
        password = self.app_config.mqtt_password
        client.username_pw_set(username, password)
        try:
            client.connect(host, port=port)
        except (ConnectionRefusedError, socket.gaierror) as e:
            _LOG.error("Could not connect to MQTT broker: %s", e)
            raise e
        self.mqtt_topics = {ID_EC: self.app_config.ec_prefix}
        client.on_connect = self.create_on_connect()
        client.on_message = self.create_on_message()

        return client

    def create_on_connect(self) -> Callable:
        """Create a callback to handle connection to MQTT broker."""

        def on_mqtt_connect(client, _userdata, _flags, _reason_code):
            # def on_connect(client, _userdata, _flags, _reason_code, _properties):
            """Subscribe to topics on connect."""
            retcodes = []
            subscribed = []
            for topic in self.mqtt_topics.values():
                retcodes.append(client.subscribe(topic))
                subscribed.append(topic)
            if all([retcode[0] == 0 for retcode in retcodes]):
                _LOG.debug("Subscribed to topics: %s", subscribed)
            else:
                _LOG.warning("Error subscribing to topics: %s", retcodes)

        return on_mqtt_connect

    def create_on_message(self) -> Callable:
        """Create a callback to handle incoming MQTT messages."""

        def on_mqtt_message(_client, _userdata, message):
            topic = message.topic
            payload = message.payload.decode("utf-8")
            _LOG.debug("Received message: %s %s", topic, payload)
            if topic == self.mqtt_topics[ID_EC]:
                try:
                    self.current_state.current_ec = float(payload)
                except ValueError as e:
                    _LOG.warning("Error getting EC: %s - %s", payload, e)
                    self.current_state.current_ec = -1.0

        return on_mqtt_message

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
                # status_json = self.current_state.status_json()
                # _LOG.debug("Publishing state: %s", status_json)
                # self.mqtt_client.publish(
                #     self.mqtt_topics[ID_STATE], status_json, qos=1, retain=True
                # )
        return

    def calibrate_ec(self):
        """Calibrate the EC sensor"""
        _LOG.info("Calibrating EC sensor")
        try:
            calibration_data: CalibrationData = run_calibration(
                self.mqttio_config_file, self.current_state.calibration_temperature
            )
            self.current_state.calibration_status = calibration_data.calibration_status
            message = calibration_data.calibration_message
        except Exception as e:
            message = f"Error calibrating EC sensor: {e}"
            _LOG.error(message)
            self.current_state.calibration_status = CalibrationStatus.ERROR
        self.current_state.calibration_status_message = message
        return

    def manual_dose(self):
        """Dose for a given duration"""
        self.ec_pump.run(self.current_state.manual_dose_duration)
        self.current_state.last_dose_time = time.time()
        self.current_state.dose_count += 1
        self.current_state.total_dose_time += self.current_state.manual_dose_duration
        # status_json = self.current_state.status_json()
        # _LOG.debug("Publishing state following manual dose: %s", status_json)
        # self.mqtt_client.publish(
        #     self.mqtt_topics[ID_STATE], status_json, qos=1, retain=True
        # )
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

            if self.current_state.calibration_status == CalibrationStatus.CALIBRATING:
                self.calibrate_ec()

            if self.current_state.manual_dose:
                self.manual_dose()

            if self.current_state.control:
                self.control_ec()

            time.sleep(self.loop_delay)


if __name__ == "__main__":
    CONFIG_FILE = "fufarm_hydro.yml"
    MQTTIO_CONFIG_FILE = "mqtt-io.yml"
    APP_CONFIG = AppConfig()
    CURRENT_STATE = AppState()
    if os.path.isfile(CONFIG_FILE):
        APP_CONFIG, CURRENT_STATE = process_config(CONFIG_FILE)

    logging.basicConfig(
        level=APP_CONFIG.log_level,
        format="%(asctime)s rpi: %(message)s",
    )

    controller = HydroController(APP_CONFIG, CURRENT_STATE, MQTTIO_CONFIG_FILE)
    controller.run()
