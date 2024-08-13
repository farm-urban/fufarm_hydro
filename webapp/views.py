"""Routing functions"""

import json
import logging
import time
from flask import jsonify
from flask import render_template
from flask import request

from util import ID_CALIBRATE, ID_CONTROL, ID_MANUAL_DOSE, ID_PARAMETERS
from . import app, app_state, mqtt, mqtt_topics


_LOG = logging.getLogger(__name__)


# pylint: disable=missing-function-docstring
@app.template_filter("format_time")
def format_time_filter(s):
    return time.asctime(time.localtime(s))


@app.route("/")
def index():
    return render_template("index.html", app_state=app_state)


@app.route("/control", methods=["POST"])
def control():
    mode = request.form["mode"]
    changed = False
    if mode == "control" and not app_state.control:
        app_state.control = True
        changed = True
    elif mode == "monitor" and app_state.control:
        app_state.control = False
        changed = True
    if changed:
        _LOG.debug("Publishing control: %s", app_state.control)
        mqtt.publish(mqtt_topics[ID_CONTROL], "1" if app_state.control else "0")

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
    if target_ec != app_state.target_ec:
        parameters["target_ec"] = target_ec
    if dose_duration != app_state.dose_duration:
        parameters["dose_duration"] = dose_duration
    if equilibration_time != app_state.equilibration_time:
        parameters["equilibration_time"] = equilibration_time

    _LOG.debug("control setting parameters: %s", parameters)
    mqtt.publish(mqtt_topics[ID_PARAMETERS], json.dumps(parameters))

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
    _LOG.debug("Publishing manual dose: %s", duration)
    mqtt.publish(mqtt_topics[ID_MANUAL_DOSE], str(duration))
    return {"status": "success"}, 200


@app.route("/calibrate_ec", methods=["POST"])
def calibrate_ec():
    check = request.form["calibrate-ecprobe-check"]
    try:
        check = int(check)
    except ValueError:
        _LOG.debug("Error getting calibrate-check: %s", check)
        data = {"status": "failure"}
        return data, 422
    _LOG.debug("Publishing calibrate ecprobe")
    mqtt.publish(mqtt_topics[ID_CALIBRATE], "ec")
    return {"status": "success"}, 200


@app.route("/status")
def status():
    return jsonify(state=app_state.status_dict())
