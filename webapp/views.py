from flask import jsonify
from flask import render_template
from flask import request

from . import app, app_state, mqtt, mqtt_topics

from util import ID_CONTROL


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
        print("Publishing control: ", app_state.control)
        mqtt.publish(mqtt_topics[ID_CONTROL], "1" if app_state.control else "0")

    # target_ec = request.form["target-ec"]
    # if target_ec:
    #     app_state.target_ec = float(target_ec)
    #     print("Publishing target_ec: ", app_state.target_ec)
    #     mqtt.publish(mqtt_topics[ID_CONTROL], str(app_state.target_ec))

    data = {"status": "success"}
    return data, 200


@app.route("/status")
def status():
    # q = request.args.get("q")
    # if q == "current_ec":
    #     return jsonify(ec=round(app_state.current_ec, 2))
    return jsonify(state=app_state.status_dict())
