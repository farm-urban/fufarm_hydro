"""Routing functions"""

# import json
import logging
import time
from flask import jsonify
from flask import render_template
from flask import request

from homehydro.hydrocontrol.state_classes import CalibrationStatus

# from mqtt_util import ID_CALIBRATE, ID_CONTROL, ID_MANUAL_DOSE, ID_PARAMETERS
# from . import app, app_state
from . import app

APP_STATE = app.config["APP_STATE"]

_LOG = logging.getLogger(__name__)


# pylint: disable=missing-function-docstring
@app.template_filter("format_time")
def format_time_filter(s):
    return time.asctime(time.localtime(s))


@app.route("/")
def index():
    return render_template("index.html", app_state=APP_STATE)


@app.route("/control", methods=["POST"])
def control():
    mode = request.form["mode"]
    changed = False
    if mode == "control" and not APP_STATE.control:
        APP_STATE.control = True
        changed = True
    elif mode == "monitor" and APP_STATE.control:
        APP_STATE.control = False
        changed = True
    if changed:
        _LOG.info("Setting control: %s", APP_STATE.control)
        # mqtt.publish(mqtt_topics[ID_CONTROL], "1" if app_state.control else "0")

    target_ec = request.form["target-ec"]
    try:
        target_ec = float(target_ec)
    except ValueError:
        _LOG.debug("Error getting target_ec: %s", target_ec)
        return {"status": "failure"}, 422
    dose_duration = request.form["dose-duration"]
    try:
        dose_duration = int(dose_duration)
    except ValueError:
        _LOG.debug("Error getting dose_duration: %s", target_ec)
        return {"status": "failure"}, 422
    equilibration_time = request.form["equilibration-time"]
    try:
        equilibration_time = int(equilibration_time)
    except ValueError:
        _LOG.debug("Error getting equilibration_time: %s", equilibration_time)
        return {"status": "failure"}, 422

    parameters = {}
    if target_ec != APP_STATE.target_ec:
        APP_STATE.target_ec = target_ec
        parameters["target_ec"] = target_ec
    if dose_duration != APP_STATE.dose_duration:
        APP_STATE.dose_duration = dose_duration
        parameters["dose_duration"] = dose_duration
    if equilibration_time != APP_STATE.equilibration_time:
        APP_STATE.equilibration_time = equilibration_time
        parameters["equilibration_time"] = equilibration_time

    _LOG.info("/control setting parameters: %s", parameters)
    # mqtt.publish(mqtt_topics[ID_PARAMETERS], json.dumps(parameters))
    # Return parameters to update the UI in case any could not be set as requested
    return jsonify(parameters=parameters)


@app.route("/dose", methods=["POST"])
def dose():
    duration = request.form["manual-dose-duration"]
    try:
        duration = int(duration)
    except ValueError:
        _LOG.debug("Error getting dose duration: %s", duration)
        data = {"status": "failure"}
        return data, 422
    _LOG.info("Setting manual dose: %s", duration)
    # mqtt.publish(mqtt_topics[ID_MANUAL_DOSE], str(duration))
    APP_STATE.manual_dose = True
    APP_STATE.manual_dose_duration = duration
    return {"status": "success"}, 200


@app.route("/calibrate_ec", methods=["POST"])
def calibrate_ec():
    temperature = request.form["calibrate-ecprobe-temperature"]
    try:
        temperature = float(temperature)
    except ValueError:
        msg = f"Invalid temperature for calibration: '{temperature}'"
        _LOG.info(msg)
        APP_STATE.calibration_status = CalibrationStatus.ERROR
        APP_STATE.calibration_message = msg
        data = {"status": "failure"}
        return data, 422
    _LOG.info("Calibrate ecprobe: %s", temperature)
    # mqtt.publish(mqtt_topics[ID_CALIBRATE], "ec")
    APP_STATE.calibration_status = CalibrationStatus.CALIBRATING
    APP_STATE.calibrate_temperature = temperature
    return {"status": "success"}, 200


@app.route("/status")
def status():
    return jsonify(state=APP_STATE.status_dict())
