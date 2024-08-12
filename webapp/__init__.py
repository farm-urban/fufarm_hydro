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
    create_on_connect,
    create_on_message,
    process_config,
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

mqtt_topics = setup_mqtt_topics(app_config)
create_on_connect(mqtt_topics, flask_decorator=mqtt.on_connect)
create_on_message(app_state, mqtt_topics, flask_decorator=mqtt.on_message)


# from js_example import views  # noqa: E402, F401
from . import views  # noqa: E402, F401
