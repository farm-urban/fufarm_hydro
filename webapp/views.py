from flask import jsonify
from flask import render_template
from flask import request

import random
import time
from . import app


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/add", methods=["POST"])
def add():
    a = request.form.get("a", 0, type=float)
    b = request.form.get("b", 0, type=float)
    return jsonify(result=a + b)


@app.route("/status")
def status():
    q = request.args.get("q")
    if q == "current_ec":
        return jsonify(ec=round(random.uniform(0.0, 3.0), 2))
    elif q == "last_dose_time":
        return jsonify(
            last_dose_time=time.strftime("%a, %d %b %Y %H:%M:%S", time.localtime())
        )
