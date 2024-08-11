import logging
import json
import time
from dataclasses import dataclass
import yaml


_LOG = logging.getLogger(__name__)

ID_CONTROL = "control"
ID_CALIBRATE = "calibrate"
ID_EC = "ec"
ID_PARAMETERS = "parameters"


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

    # host = "homeassistant.local"
    host: str = "localhost"
    port: int = 1883
    username: str = "hamqtt"
    password: str = "UbT4Rn3oY7!S9L"
    topic_prefix: str = "hydro"
    ec_prefix: str = "sensors/sensor/ec1"
    motor_pin: int = 0
    log_level: str = "INFO"

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


def setup_mqtt_topics(app_config: AppConfig) -> dict[str, str]:
    """Setup the MQTT topics."""
    separator = "/"
    return {
        ID_CONTROL: separator.join([app_config.topic_prefix, ID_CONTROL]),
        ID_CALIBRATE: separator.join([app_config.topic_prefix, ID_CALIBRATE]),
        ID_EC: app_config.ec_prefix,
        ID_PARAMETERS: separator.join([app_config.topic_prefix, ID_PARAMETERS]),
    }


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
