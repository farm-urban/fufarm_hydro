"""Functions shared between command-line and flask app"""

from enum import IntEnum
import logging
import json
import time
from dataclasses import dataclass
import yaml


def process_config(
    file_path,
):
    """Process the configuration file."""
    with open(file_path, "r", encoding="utf-8") as f:
        yamls = yaml.safe_load(f)
        if "app" in yamls:
            _app_config = AppConfig(**yamls["app"])
        if "state" in yamls:
            _current_state = AppState(**yamls["state"])

    if not hasattr(logging, _app_config.log_level):
        raise AttributeError(f"Unknown log_level: {_app_config.APP.log_level}")

    return _app_config, _current_state


@dataclass
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
    motor_pin: int = 0
    log_level: str = "INFO"

    def __repr__(self):
        x = "\n ".join(f"{k} : {repr(v)}" for (k, v) in self.__dict__.items())
        return f"<\n{x}\n>"


class CalibrationStatus(IntEnum):
    """Enum for calibration status."""

    NOT_CALIBRATED = 0
    CALIBRATING = 1
    CALIBRATED = 2
    ERROR = 3


@dataclass
class AppState:
    """Tracks the current state of the autodoser."""

    # Control variables
    control: bool = False
    calibration_temperature: float = 25.0
    calibration_status: CalibrationStatus = CalibrationStatus.NOT_CALIBRATED
    calibration_status_message: str = "Not Calibrated"
    manual_dose: bool = False
    manual_dose_duration: int = 0
    equilibration_time: int = 3
    target_ec: float = 1.8
    dose_duration: int = 5
    # State variables
    current_ec: float = 10.0  # Set to a high value to prevent dosing before reading EC
    dose_count: int = 0
    last_dose_time: float = time.time() - equilibration_time
    total_dose_time: float = 0

    def status_dict(self):
        """Return the status variables as a dictionary."""
        return dict(
            {
                "calibration_temperature": self.calibration_temperature,
                "calibration_status": self.calibration_status,
                "current_ec": self.current_ec,
                "dose_count": self.dose_count,
                # "last_dose_time": time.strftime(
                #     "%a, %d %b %Y %H:%M:%S", time.localtime(self.last_dose_time)
                # ),
                "last_dose_time": self.last_dose_time,
                "total_dose_time": self.total_dose_time,
            }
        )

    def status_json(self):
        """Return status as json string"""
        return json.dumps(self.status_dict())

    def __repr__(self):
        x = "\n ".join(f"{k} : {repr(v)}" for (k, v) in self.__dict__.items())
        return f"<\n{x}\n>"
