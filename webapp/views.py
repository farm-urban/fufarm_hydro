from flask import jsonify
from flask import render_template
from flask import request
import logging

from . import app, app_state, mqtt, mqtt_topics

from util import ID_CALIBRATE, ID_CONTROL, ID_MANUAL_DOSE

_LOG = logging.getLogger(__name__)


@app.route("/")
def index():
    return render_template("index.html")


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

    # target_ec = request.form["target-ec"]
    # if target_ec:
    #     app_state.target_ec = float(target_ec)
    #     print("Publishing target_ec: ", app_state.target_ec)
    #     mqtt.publish(mqtt_topics[ID_CONTROL], str(app_state.target_ec))

    return {"status": "success"}, 200


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
    # q = request.args.get("q")
    # if q == "current_ec":
    #     return jsonify(ec=round(app_state.current_ec, 2))
    return jsonify(state=app_state.status_dict())
