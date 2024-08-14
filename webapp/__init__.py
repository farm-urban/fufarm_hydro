""""Main Flask App"""

import inspect
import logging
import os
import socket
import sys
import threading
import time

from flask import Flask
from flask_mqtt import Mqtt

from state_classes import process_config


# Hack import for time being
currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
PARENT_DIR = os.path.dirname(currentdir)
sys.path.insert(0, PARENT_DIR)
# pylint: disable=wrong-import-position
from mqtt_util import (
    ID_STATE,
    create_on_connect,
    create_on_message,
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

try:
    mqtt = Mqtt(app)
except socket.gaierror as e:
    _LOG.error("Error connecting to MQTT broker: %s", e)
    sys.exit(1)

mqtt_topics = setup_mqtt_topics(app_config)
create_on_connect([ID_STATE], mqtt_topics, flask_decorator=mqtt.on_connect)
create_on_message(app_state, mqtt_topics, flask_decorator=mqtt.on_message)


# def myloop(app_state: AppState):
#     """Test loop"""
#     while True:
#         print(app_state)
#         time.sleep(5)

# thread = threading.Thread(target=myloop, args=(app_state,))
# thread.start()


# from js_example import views  # noqa: E402, F401
from . import views  # noqa: E402, F401
