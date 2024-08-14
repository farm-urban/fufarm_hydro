""""Main Flask App"""

import inspect
import logging
import os
import threading

from flask import Flask
from webapp.hydrocontrol.state_classes import process_config
import webapp.hydrocontrol.controller as controller

CURRENT_DIR = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
CONFIG_FILE = os.path.join(PARENT_DIR, "homehydro.yml")
app_config, app_state = process_config(CONFIG_FILE)

logging.basicConfig(
    level=app_config.log_level,
    format="%(asctime)s rpi: %(message)s",
)


app = Flask(__name__)
app.config["MQTT_BROKER_URL"] = app_config.host
app.config["MQTT_BROKER_PORT"] = app_config.port
app.config["MQTT_USERNAME"] = app_config.username
app.config["MQTT_PASSWORD"] = app_config.password


hydro_controller = controller.HydroController(app_config, app_state)
thread = threading.Thread(target=hydro_controller.run)
thread.start()

from . import views  # noqa: E402, F401
