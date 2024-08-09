import logging
import time
import yaml
from dataclasses import dataclass


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

    if not hasattr(logging, _app_config.log_level):
        raise AttributeError(f"Unknown log_level: {_app_config.APP.log_level}")

    return _app_config, _current_state


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
