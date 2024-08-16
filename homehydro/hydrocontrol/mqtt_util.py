"""Functions shared between command-line and flask app"""

import logging
import json
from typing import Callable, List

from homehydro.hydrocontrol.state_classes import AppConfig, AppState


_LOG = logging.getLogger(__name__)

# MQTT topics
ID_CONTROL = "control"
ID_CALIBRATE = "calibrate_ec"
ID_EC = "ec"
ID_MANUAL_DOSE = "manual_dose"
ID_PARAMETERS = "parameters"
ID_STATE = "state"
# Individual parametsrs
ID_LAST_DOSE_TIME = "last_dose_time"
ID_DOSE_COUNT = "dose_count"
ID_TOTAL_DOSE_TIME = "total_dose_time"


def setup_mqtt_topics(app_config: AppConfig) -> dict[str, str]:
    """Setup the MQTT topics."""
    separator = "/"
    return {
        ID_CONTROL: separator.join([app_config.topic_prefix, ID_CONTROL]),
        ID_CALIBRATE: separator.join([app_config.topic_prefix, ID_CALIBRATE]),
        ID_EC: app_config.ec_prefix,
        ID_MANUAL_DOSE: separator.join([app_config.topic_prefix, ID_MANUAL_DOSE]),
        ID_PARAMETERS: separator.join([app_config.topic_prefix, ID_PARAMETERS]),
        ID_STATE: separator.join([app_config.topic_prefix, ID_STATE]),
    }


def create_on_connect(
    subscribe_list: List[str],
    mqtt_topics: dict[str, str],
    flask_decorator: Callable = None,
) -> Callable:
    """Create a callback to handle connection to MQTT broker."""

    # @mqtt.on_connect()
    def on_mqtt_connect(client, _userdata, _flags, _reason_code):
        # def on_connect(client, _userdata, _flags, _reason_code, _properties):
        """Subscribe to topics on connect."""
        retcodes = []
        subscribed = []
        for name, topic in mqtt_topics.items():
            if name in subscribe_list:
                retcodes.append(client.subscribe(topic))
                subscribed.append(topic)
        if all([retcode[0] == 0 for retcode in retcodes]):
            _LOG.debug("Subscribed to topics: %s", subscribed)
        else:
            _LOG.warning("Error subscribing to topics: %s", retcodes)

    if flask_decorator:
        # Not sure how to call the decorator when it's an object method
        # on_mqtt_connect = flask_decorator(on_mqtt_connect)
        @flask_decorator()
        def decorated_on_mqtt_connect(client, _userdata, _flags, _reason_code):
            return on_mqtt_connect(client, _userdata, _flags, _reason_code)

    if flask_decorator:
        return decorated_on_mqtt_connect
    else:
        return on_mqtt_connect


def create_on_message(
    state: AppState, mqtt_topics: dict[str, str], flask_decorator: Callable = None
) -> Callable:
    """Create a callback to handle incoming MQTT messages."""

    # @mqtt.on_message()
    def on_mqtt_message(_client, _userdata, message):
        topic = message.topic
        payload = message.payload.decode("utf-8")
        _LOG.debug("Received message: %s %s", topic, payload)
        if topic == mqtt_topics[ID_CALIBRATE]:
            if payload == "ec":
                state.should_calibrate_ec = True
            else:
                _LOG.warning("Invalid payload for calibrate topic: %s", payload)
        elif topic == mqtt_topics[ID_CONTROL]:
            if payload == "0":
                state.control = False
            elif payload == "1":
                state.control = True
            else:
                _LOG.warning("Invalid payload for control topic: %s", payload)
        elif topic == mqtt_topics[ID_EC]:
            try:
                state.current_ec = float(payload)
            except ValueError as e:
                _LOG.warning("Error getting EC: %s - %s", payload, e)
                state.current_ec = -1.0
        elif topic == mqtt_topics[ID_MANUAL_DOSE]:
            try:
                state.manual_dose_duration = int(payload)
            except ValueError as e:
                _LOG.warning("Error getting manual dose duration: %s - %s", payload, e)
                state.manual_dose = False
                state.manual_dose_duration = 0
                return
            state.manual_dose = True
        elif topic == mqtt_topics[ID_PARAMETERS]:
            variables = ["dose_duration", "equilibration_time", "target_ec"]
            process_variables(payload, state, variables)
        elif topic == mqtt_topics[ID_STATE]:
            variables = [
                "current_ec",
                "dose_count",
                "last_dose_time",
                "total_dose_time",
            ]
            process_variables(payload, state, variables)

    # End of on_message
    if flask_decorator:
        # Not sure how to call the decorator when it's an object method
        # on_mqtt_message = flask_decorator(on_mqtt_message)
        @flask_decorator()
        def decorated_on_mqtt_message(_client, _userdata, message):
            return on_mqtt_message(_client, _userdata, message)

    if flask_decorator:
        return decorated_on_mqtt_message
    else:
        return on_mqtt_message


def process_entries(state: AppState, data: dict, keys: List[str]):
    "Helper function"
    for k in keys:
        if k in data:
            setattr(state, k, data[k])
        else:
            _LOG.warning(
                "process_entries: could not find key '%s' in data: %s", k, data.keys()
            )


def process_variables(payload: str, state: AppState, variables: List[str]):
    """Process the variables from an MQTT message."""
    _LOG.debug("Processing variable update: %s for keys: %s", payload, variables)
    try:
        data = json.loads(payload)
    except json.decoder.JSONDecodeError as e:
        _LOG.warning(
            "Error decoding PARAMETERS data to JSON: %s\nMessage was: %s",
            e.msg,
            e.doc,
        )
    process_entries(state, data, variables)
