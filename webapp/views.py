from flask import jsonify
from flask import render_template

from . import app, app_state


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/status")
def status():
    # from flask import request
    # q = request.args.get("q")
    # if q == "current_ec":
    #     return jsonify(ec=round(app_state.current_ec, 2))
    return jsonify(state=app_state.status_dict())
