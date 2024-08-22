""""Main Flask App"""

import logging
import os
import threading
from argparse import ArgumentParser

from homehydro.hydrocontrol.state_classes import process_config
import homehydro.hydrocontrol.controller as controller

from . import app

parser = ArgumentParser()
parser.add_argument(
    "-c", "--config", required=True, dest="app_config", help="Path to the config file"
)
parser.add_argument(
    "-d", "--debug", action="store_true", dest="debug", help="Turn on debug mode"
)
parser.add_argument(
    "-m",
    "--mqttio-config",
    required=True,
    dest="mqttio_config_file",
    help="Path to the MQTT-IO config file",
)
args = parser.parse_args()
config_file = args.app_config
mqttio_config_file = args.mqttio_config_file
app_config, app_state = process_config(config_file)

logging.basicConfig(
    level=app_config.log_level,
    format="%(asctime)s rpi: %(message)s",
)

app.config["APP_STATE"] = app_state

# In debug mode flask forks intself so we don't want to start the controller twice
# https://raspberrypi.stackexchange.com/questions/148825/lgpio-gpio-setup-fails-with-gpio-not-allocated-when-run-from-a-flask-app
MAIN_LOOP = False
if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
    MAIN_LOOP = True
    hydro_controller = controller.HydroController(
        app_config, app_state, mqttio_config_file
    )
    thread = threading.Thread(target=hydro_controller.run)

from . import views  # noqa: E402, F401

if __name__ == "__main__":
    if MAIN_LOOP:
        thread.start()
    app.run(host=app_config.flask_host, debug=args.debug)
