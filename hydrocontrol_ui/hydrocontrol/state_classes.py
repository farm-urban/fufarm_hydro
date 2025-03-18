"""Functions shared between command-line and flask app"""

import logging
import json
import time
import dataclasses
import sys
from typing import Union
import yaml

from hydrocontrol_ui.hydrocontrol.ec_calibrator import (
    CalibrationData,
    read_calibration,
)

_LOG = logging.getLogger()

PY310 = sys.version_info >= (3, 10)


def process_config(
    file_path,
):
    """Process the configuration file."""
    with open(file_path, "r", encoding="utf-8") as f:
        yamls = yaml.safe_load(f)
        if not "app" in yamls and not "state" in yamls:
            raise AttributeError("Config file must contain 'app' and 'state' sections")
        _app_config = AppConfig(**yamls["app"])
        _current_state = AppState(**yamls["state"])

    if not hasattr(logging, _app_config.log_level):
        raise AttributeError(f"Unknown log_level: {_app_config.APP.log_level}")

    calibration_data = read_calibration(_app_config.ec_calibration_file)
    _LOG.debug(
        "Read calibration File: %s - data: %s",
        _app_config.ec_calibration_file,
        calibration_data,
    )
    _current_state.calibration_data = calibration_data

    return _app_config, _current_state


@dataclasses.dataclass(**({"slots": True} if PY310 else {}))
class AppConfig:
    """Configures the Application."""

    flask_host: str = "0.0.0.0"
    # host = "homeassistant.local"
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_username: str = "hamqtt"
    mqtt_password: str = "UbT4Rn3oY7!S9L"
    topic_prefix: str = "hydro"
    ec_prefix: str = "sensors/sensor/ec1"
    motor_channel: int = 0
    ec_calibration_file: str = "./ec-config.json"
    mqttio_config_file: str = "./mqtt-io.yml"
    log_level: str = "INFO"

    def __repr__(self):
        x = "\n ".join(f"{k} : {repr(v)}" for (k, v) in self.__dict__.items())
        return f"<\n{x}\n>"


@dataclasses.dataclass(**({"slots": True} if PY310 else {}))
class AppState:
    """Tracks the current state of the autodoser."""

    # Control variables
    control: bool = False
    calibration_data: Union[CalibrationData, None] = None
    manual_dose: bool = False
    manual_dose_duration: int = 0
    equilibration_time: int = 3
    target_ec: float = 1.8
    dose_duration: int = 5
    # State variables
    current_ec: float = 999.0  # Set to a high value to prevent dosing before reading EC
    dose_count: int = 0
    last_dose_time: float = time.time() - equilibration_time
    total_dose_time: float = 0

    def status_dict(self):
        """Return the variables as a dictionary."""
        return dataclasses.asdict(self)

    def status_json(self):
        """Return status as json string"""
        return json.dumps(self.status_dict())

    def __repr__(self):
        x = "\n ".join(f"{k} : {repr(v)}" for (k, v) in self.__dict__.items())
        return f"<\n{x}\n>"
