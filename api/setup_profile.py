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
            "text": "مرحبًا! اكتب أي سؤال أو استخدم الأزرار بالأسفل."
        }],
        "get_started": {"payload": "GET_STARTED"},
        "persistent_menu": [{
            "locale": "default",
            "composer_input_disabled": False,
            "call_to_actions": [
                {"type": "postback", "title": "🤖 معلومات الذكاء", "payload": "AI_INFO"},
                {"type": "postback", "title": "🧭 قائمة", "payload": "SHOW_MENU"},
                {"type": "web_url", "title": "👨‍💻 حساب المطوّر", "url": DEV_PROFILE_URL}
            ]
        }],
        "ice_breakers": [
            {"question": "ما الذي يمكنك فعله؟", "payload": "AI_INFO"},
            {"question": "أظهر القائمة", "payload": "SHOW_MENU"},
            {"question": "من مطوّرك؟", "payload": "DEV_INFO"}
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
