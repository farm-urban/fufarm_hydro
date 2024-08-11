from typing import Callable
from flask import Flask
from flask_mqtt import Mqtt

import logging
import os
import sys
import inspect

# Hack import for time being
currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
PARENT_DIR = os.path.dirname(currentdir)
sys.path.insert(0, PARENT_DIR)
from stateclass import (
    ID_CALIBRATE,
    ID_CONTROL,
    ID_EC,
    ID_PARAMETERS,
    State,
    process_config,
    process_parameters,
    setup_mqtt_topics,
)


CONFIG_FILE = os.path.join(PARENT_DIR, "fufarm_hydro.yml")
app_config, app_state = process_config(CONFIG_FILE)

logging.basicConfig(
    level=app_config.log_level,
    format="%(asctime)s rpi: %(message)s",
)
_LOG = logging.getLogger()


app = Flask(__name__)
app.config["MQTT_BROKER_URL"] = app_config.host
app.config["MQTT_BROKER_PORT"] = app_config.port
app.config["MQTT_USERNAME"] = app_config.username
app.config["MQTT_PASSWORD"] = app_config.password

mqtt = Mqtt(app)


def create_on_connect(mqtt_topics: dict[str, str]):
    """Create a callback to handle connection to MQTT broker."""

    @mqtt.on_connect()
    def on_connect(client, _userdata, _flags, _reason_code):
        # def on_connect(client, _userdata, _flags, _reason_code, _properties):
        """Subscribe to topics on connect."""
        retcodes = []
        for topic in mqtt_topics.values():
            retcodes.append(client.subscribe(topic))
        if all([retcode[0] == 0 for retcode in retcodes]):
            _LOG.debug("Subscribed to topics: %s", [v for v in mqtt_topics.values()])
        else:
            _LOG.warning("Error subscribing to topics: %s", retcodes)

    return on_connect


def create_on_message(state: State, mqtt_topics: dict[str, str]) -> Callable:
    """Create a callback to handle incoming MQTT messages."""

    @mqtt.on_message()
    def on_message(_client, _userdata, message):
        topic = message.topic
        payload = message.payload.decode("utf-8")
        _LOG.debug("Received message: %s %s", topic, payload)
        if topic == mqtt_topics[ID_CALIBRATE]:
            if payload == "ec":
                state.should_calibrate = True
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
        elif topic == mqtt_topics[ID_PARAMETERS]:
            process_parameters(payload, state)

    # End of on_message

    return on_message


mqtt_topics = setup_mqtt_topics(app_config)
create_on_connect(mqtt_topics)
create_on_message(app_state, mqtt_topics)


# from js_example import views  # noqa: E402, F401
from . import views  # noqa: E402, F401
