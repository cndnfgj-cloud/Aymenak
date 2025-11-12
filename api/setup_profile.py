import os
import requests
from flask import Flask, jsonify

app = Flask(__name__)
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "")
DEV_PROFILE_URL = os.getenv("DEV_PROFILE_URL", "https://www.facebook.com/aymen.bourai.2025")

def call_profile(payload):
    url = f"https://graph.facebook.com/v17.0/me/messenger_profile?access_token={PAGE_ACCESS_TOKEN}"
    r = requests.post(url, json=payload, timeout=30)
    try:
        return r.json()
    except Exception:
        return {"status": r.status_code, "text": r.text}

@app.route("/api/setup/profile", methods=["POST", "GET"])
def setup_profile():
    payload = {
        "greeting": [{
            "locale": "default",
            "text": "أهلًا! اكتب أي سؤال — رد فوري وقصير."
        }],
        "get_started": {"payload": "GET_STARTED"},
        # No persistent_menu per request
        "ice_breakers": [
            {"question": "من مطوّرك؟", "payload": "DEV_INFO"},
            {"question": "أرني زر المشاركة", "payload": "SHARE_BOT"}
        ]
    }
    return jsonify(call_profile(payload))

@app.route("/api/setup/delete", methods=["POST", "GET"])
def delete_profile():
    url = f"https://graph.facebook.com/v17.0/me/messenger_profile?access_token={PAGE_ACCESS_TOKEN}"
    r = requests.delete(url, json={"fields": ["greeting","get_started","persistent_menu","ice_breakers"]}, timeout=30)
    try:
        return r.json()
    except Exception:
        return {"status": r.status_code, "text": r.text}

@app.route("/api/healthz")
def healthz():
    return jsonify({"ok": True})
