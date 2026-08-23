from flask import Flask, jsonify, request
from slack_bolt.adapter.flask import SlackRequestHandler

from slack_app import create_app


app = Flask(__name__)
slack_handler = SlackRequestHandler(create_app())


@app.route("/", methods=["GET"])
@app.route("/<path:path>", methods=["GET"])
def health_check(path=""):
    return jsonify({"status": "ok"})


@app.route("/", methods=["POST"])
@app.route("/<path:path>", methods=["POST"])
def slack_events(path=""):
    return slack_handler.handle(request)
