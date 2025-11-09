import os
import json
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ===== إعدادات أساسية =====
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "boykta 2023")
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyD6QwvrvnjU7j-R6fkOghfIVKwtvc7SmLk")

# ===== دالة الرد عبر Facebook Messenger =====
def send_message(recipient_id, text):
    url = f"https://graph.facebook.com/v17.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text}
    }
    headers = {"Content-Type": "application/json"}
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=15)
        print("تم إرسال الرد:", r.text)
    except Exception as e:
        print("خطأ في إرسال الرد:", e)

# ===== دالة الذكاء الاصطناعي (Gemini API) =====
def get_gemini_reply(user_message):
    url = "https://firebasevertexai.googleapis.com/v1beta/projects/gemmy-ai-bdc03/locations/us-central1/publishers/google/models/gemini-2.0-flash-lite:generateContent"
    payload = {
        "model": "projects/gemmy-ai-bdc03/locations/us-central1/publishers/google/models/gemini-2.0-flash-lite",
        "contents": [
            {"role": "user", "parts": [{"text": user_message}]}
        ]
    }
    headers = {
        "User-Agent": "Ktor client",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_API_KEY,
        "x-goog-api-client": "gl-kotlin/2.2.0-ai fire/16.5.0",
        "x-firebase-appid": "1:652803432695:android:c4341db6033e62814f33f2",
        "x-firebase-appversion": "79",
        "x-firebase-appcheck": "eyJlcnJvciI6IlVOS05PV05fRVJST1IifQ=="
    }

    try:
        r = requests.post(url, data=json.dumps(payload), headers=headers, timeout=30)
        data = r.json()
        reply = data["candidates"][0]["content"]["parts"][0]["text"]
        return reply
    except Exception as e:
        print("خطأ في Gemini:", e)
        return "حدث خطأ أثناء الاتصال بالذكاء الاصطناعي ⚠️"

# ===== التحقق من Webhook =====
@app.route("/api/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "خطأ في التحقق من Webhook", 403

# ===== استقبال رسائل المستخدم =====
@app.route("/api/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    if data.get("object") != "page":
        return jsonify({"status": "ignored"}), 200

    for entry in data.get("entry", []):
        for event in entry.get("messaging", []):
            sender = event.get("sender", {}).get("id")
            if not sender:
                continue
            if "message" in event and "text" in event["message"]:
                user_message = event["message"]["text"]
                print(f"رسالة من المستخدم {sender}: {user_message}")
                ai_reply = get_gemini_reply(user_message)
                send_message(sender, ai_reply)
    return jsonify({"status": "ok"}), 200

# ===== نقطة فحص جاهزية =====
@app.route("/api/healthz", methods=["GET"])
def health():
    return jsonify({"ok": True, "status": "Bot is running 🚀"})

# ========== النهاية ==========
