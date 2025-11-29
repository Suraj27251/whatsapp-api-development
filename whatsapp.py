import os
import sqlite3
import json
import requests
from datetime import datetime
from flask import Blueprint, request, jsonify, send_from_directory, current_app

# CONFIG
DB_PATH = "complaints.db"
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
WHATSAPP_API_URL = "https://graph.facebook.com/v17.0"

# Blueprint
whatsapp_bp = Blueprint("whatsapp_bp", __name__)


# --------------------------
# DB Setup
# --------------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS whatsapp_incoming (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            mobile TEXT,
            message TEXT,
            created_at TEXT,
            raw_json TEXT
        )
    """)
    conn.commit()
    conn.close()


@whatsapp_bp.before_app_first_request
def setup():
    init_db()


# --------------------------
# Send Template Function
# --------------------------
def send_whatsapp_template(mobile, template_name, components):
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        return {"error": "Missing env variables"}

    url = f"{WHATSAPP_API_URL}/{WHATSAPP_PHONE_NUMBER_ID}/messages"

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": mobile,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": "en_US"},
            "components": components
        }
    }

    try:
        r = requests.post(url, json=payload, headers=headers)
        return r.json()
    except Exception as e:
        return {"error": str(e)}


# --------------------------
# INDEX PAGE (No templates folder)
# --------------------------
@whatsapp_bp.route("/")
def index():
    return send_from_directory(".", "index.html")


# --------------------------
# WHATSAPP WEBHOOK
# --------------------------
@whatsapp_bp.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        return request.args.get("hub.challenge", ""), 200

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "empty"}), 400

    try:
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                contacts = value.get("contacts", [])
                messages = value.get("messages", [])

                if contacts and messages:
                    name = contacts[0].get("profile", {}).get("name", "Unknown")
                    mobile = contacts[0]["wa_id"]
                    msg = messages[0].get("text", {}).get("body", "")
                    ts = messages[0]["timestamp"]
                    created = datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")

                    conn = sqlite3.connect(DB_PATH)
                    c = conn.cursor()
                    c.execute("""
                        INSERT INTO whatsapp_incoming (name, mobile, message, created_at, raw_json)
                        VALUES (?, ?, ?, ?, ?)
                    """, (name, mobile, msg, created, json.dumps(value)))
                    conn.commit()
                    conn.close()

        return jsonify({"status": "ok"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --------------------------
# FETCH WEBHOOK DATA
# --------------------------
@whatsapp_bp.route("/api/webhooks")
def get_webhooks():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM whatsapp_incoming ORDER BY id DESC LIMIT 200")
    rows = c.fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


# --------------------------
# SEND TEMPLATE API
# --------------------------
@whatsapp_bp.route("/api/send-template", methods=["POST"])
def send_temp():
    data = request.get_json(silent=True) or {}
    record_id = data.get("id")
    template = data.get("template", "complaint_received")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT mobile, name FROM whatsapp_incoming WHERE id=?", (record_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        return jsonify({"error": "invalid id"}), 404

    mobile, name = row

    components = [
        {"type": "body", "parameters": [
            {"type": "text", "text": name},
            {"type": "text", "text": str(record_id)}
        ]}
    ]

    res = send_whatsapp_template(mobile, template, components)
    return jsonify(res)
