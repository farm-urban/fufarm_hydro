from flask import Flask
from flask_mqtt import Mqtt

import os
import sys
import inspect

# Hack import for time being
currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0, parentdir)
from stateclass import State, AppConfig, process_config  # noqa: E402, F401

CONFIG_FILE = "fufarm_hydro.yml"
if os.path.isfile(CONFIG_FILE):
    app_config, mqtt_state = process_config(CONFIG_FILE)

app = Flask(__name__)
app.config["MQTT_BROKER_URL"] = app_config.host
app.config["MQTT_BROKER_PORT"] = app_config.port
app.config["MQTT_USERNAME"] = app_config.username
app.config["MQTT_PASSWORD"] = app_config.password

mqtt = Mqtt()


SEPARATOR = "/"
CALIBRATE = "calibrate"
CONTROL = "control"
EC = "ec"
PARAMETERS = "parameters"
TOPICS = {
    CONTROL: SEPARATOR.join([app_config.topic_prefix, CONTROL]),
    CALIBRATE: SEPARATOR.join([app_config.topic_prefix, CALIBRATE]),
    EC: app_config.ec_prefix,
    PARAMETERS: SEPARATOR.join([app_config.topic_prefix, PARAMETERS]),
}


@mqtt.on_connect()
def handle_connect(client, userdata, flags, rc):
    mqtt.subscribe("home/mytopic")


@mqtt.on_message()
def handle_mqtt_message(client, userdata, message):
    data = dict(topic=message.topic, payload=message.payload.decode())


# from js_example import views  # noqa: E402, F401
from . import views  # noqa: E402, F401
