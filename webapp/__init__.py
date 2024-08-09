from flask import Flask
from flask_mqtt import Mqtt

import os
import sys
import inspect

# Hack import for time being
currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0, parentdir)
from stateclass import State, AppConfig


app = Flask(__name__)
app.config["MQTT_BROKER_URL"] = "broker.hivemq.com"  # use the free broker from HIVEMQ
app.config["MQTT_BROKER_PORT"] = 1883  # default port for non-tls connection
app.config["MQTT_USERNAME"] = (
    ""  # set the username here if you need authentication for the broker
)
app.config["MQTT_PASSWORD"] = (
    ""  # set the password here if the broker demands authentication
)

mqtt = Mqtt()

mqtt_state = State()
app_config = AppConfig()

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
