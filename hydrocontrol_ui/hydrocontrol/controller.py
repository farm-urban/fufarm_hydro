"""Farm Urban Hydroponics Control System               

"""

import logging
import os
import socket
import subprocess
import sys
import time
from typing import Callable

import paho.mqtt.client as mqtt
from mqtt_io.modules.sensor.drivers.dfr0566_driver import (
    DFRobotExpansionBoardIIC,
    DFRobotExpansionBoardServo,
)

from hydrocontrol_ui.hydrocontrol.state_classes import (
    AppConfig,
    AppState,
    process_config,
)
from hydrocontrol_ui.hydrocontrol.ec_calibrator import (
    CalibrationStatus,
    run_calibration,
)


ID_EC = "ec"
_LOG = logging.getLogger()


class Pump:
    """Class for running peristaltic dosing pump"""

    def __init__(self, channel: int):
        self.mock = False
        self.channel = channel
        try:
            board = DFRobotExpansionBoardIIC(
                1, 0x10
            )  # Select i2c bus 1, set address to 0x10
        except ModuleNotFoundError as e:
            _LOG.error("Error importing pump driver modules: %s", e)
            self.mock = True

        if not self.mock:
            self.servo = DFRobotExpansionBoardServo(board)
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


class MqttIo:
    """Handles controlling an mqtt-io process"""

    def __init__(self, config_file):
        if not os.path.isfile(config_file):
            raise FileNotFoundError(f"Cannot find config file: {config_file}")
        self.config_file = config_file
        self.process = None
        # self.mqtt_logfile = None

    def start(self):
        """Start the mqtt-io process"""
        mqtt_logfile_name = "mqtt_io.log"
        # Need to think about the best place to close the filehandle
        mqtt_logfile = open(mqtt_logfile_name, mode="w", encoding="utf-8")
        self.process = subprocess.Popen(
            [sys.executable, "-m", "mqtt_io", self.config_file],
            stdout=mqtt_logfile,
            stderr=subprocess.STDOUT,
            close_fds=True,
        )
        _LOG.debug("Started MQTT-IO process: %s", self.process)
        if not self.running():
            raise RuntimeError(
                f"Problem starting MQTT IO process. Check log {mqtt_logfile_name}"
            )

    def restart(self):
        """Restart the mqtt-io process"""
        if self.running():
            self.process.kill()
        else:
            _LOG.warning("MQTT_IO restart - process wasn't running.")
        self.start()

    def running(self):
        """Check if the mqtt-io process is running"""
        self.process.poll()
        return self.process.returncode is None


class HydroController:
    """Hydroponic controller"""

    def __init__(self, app_config: AppConfig, current_state: AppState):
        self.current_state = current_state
        self.app_config = app_config
        self.loop_delay = 3

        self.mqttio_controller = MqttIo(self.app_config.mqttio_config_file)
        self.mqtt_client = self.setup_mqtt()
        self.ec_pump = Pump(app_config.motor_channel)

    def setup_mqtt(self):
        """Setup the MQTT client and subscribe to topics."""
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
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

        def on_mqtt_connect(
            client: mqtt.Client, _userdata, _connect_flags, _reason_code, _properties
        ):
            """Subscribe to topics on connect."""
            retcodes = []
            subscribed = []
            for topic in self.mqtt_topics.values():
                retcodes.append(client.subscribe(topic))
                subscribed.append(topic)
            if all((retcode[0] == 0 for retcode in retcodes)):
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

    def calibrate_ec(self):
        """Calibrate the EC sensor"""
        _LOG.info("Calibrating EC sensor")
        try:
            run_calibration(
                self.current_state.calibration_data, self.app_config.mqttio_config_file
            )
            # self.current_state.calibration_status = calibration_data.status
            # message = calibration_data.message
        except Exception as e:
            message = f"Error calibrating EC sensor: {e}"
            _LOG.error(message)
            self.current_state.calibration_data.status = CalibrationStatus.ERROR
            self.current_state.calibration_data.message = message

        if self.current_state.calibration_data.status == CalibrationStatus.CALIBRATED:
            self.mqttio_controller.restart()

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

    def run(self):
        """Run the hydro controller"""
        self.mqtt_client.loop_start()
        self.mqttio_controller.start()
        while True:
            while not self.mqtt_client.is_connected():
                _LOG.warning("mqtt_client not connected")
                self.mqtt_client.reconnect()
                time.sleep(2)

            if not self.mqttio_controller.running():
                _LOG.warning("MQTT IO process isn't running!")
            # _LOG.debug("%s %s", id(self.current_state), self.current_state)

            if (
                self.current_state.calibration_data.status
                == CalibrationStatus.CALIBRATING
            ):
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

    controller = HydroController(APP_CONFIG, CURRENT_STATE)
    controller.run()
