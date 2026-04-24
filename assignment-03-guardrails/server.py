"""
Backend server for the stock_info Chrome plugin.
Wraps agent.py and exposes it as a REST API.

Before running:
    pip install flask flask-cors
    Ensure agent.py dependencies are also installed.

Run with:
    python server.py
"""
import contextlib
import io
import traceback

from flask import Flask, jsonify, request
from flask_cors import CORS

from agent import run_agent

app = Flask(__name__)
CORS(app)  # Allow Chrome extension origins


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/query", methods=["POST"])
def query():
    data = request.get_json(force=True)
    user_query = (data.get("query") or "").strip()

    if not user_query:
        return jsonify({"error": "No query provided."}), 400

    captured = io.StringIO()
    answer = None

    try:
        with contextlib.redirect_stdout(captured):
            answer = run_agent(user_query, verbose=True)
    except Exception:
        logs = captured.getvalue()
        return jsonify({"error": traceback.format_exc(), "logs": logs}), 500

    logs = captured.getvalue()

    if answer is None:
        return jsonify({
            "answer": "The agent could not complete the task (max iterations reached).",
            "logs": logs,
        })

    return jsonify({"answer": answer, "logs": logs})


if __name__ == "__main__":
    print("Stock Info backend running on http://127.0.0.1:5001")
    app.run(debug=True, port=5001, host="127.0.0.1")
