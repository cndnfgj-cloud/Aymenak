import os
import json
import requests
from datetime import datetime, timedelta, timezone
from dateutil import parser
from flask import Flask, request, jsonify

# -----------------------------
# Env & constants
# -----------------------------
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "boykta 2023")
DEVICE_ID = os.getenv("DEVICE_ID", "B4A13AE09F22A2A4")

# Chat Smith / Vulcan settings
MAX_CHAT_HISTORY = int(os.getenv("MAX_CHAT_HISTORY", "100"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "0"))  # keep 0 as in the original

# -----------------------------
# App
# -----------------------------
app = Flask(__name__)

# -----------------------------
# In-memory stores (stateless on serverless cold starts)
# -----------------------------
user_chats = {}
access_token_data = {"token": "", "expiry": datetime.now(timezone.utc)}

# -----------------------------
# Helpers: Vulcan token & chat
# -----------------------------
def get_access_token(force_refresh=False):
    global access_token_data
    if (
        not force_refresh
        and access_token_data["token"]
        and access_token_data["expiry"] > datetime.now(timezone.utc)
    ):
        return access_token_data["token"]

    url = "https://api.vulcanlabs.co/smith-auth/api/v1/token"
    payload = {
        "device_id": DEVICE_ID,
        "order_id": "",
        "product_id": "",
        "purchase_token": "",
        "subscription_id": "",
    }
    headers = {
        "User-Agent": "Chat Smith Android, Version 4.0.5(1032)",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "x-vulcan-application-id": "com.smartwidgetlabs.chatgpt",
        "x-vulcan-request-id": "9149487891757687027212",
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        data = response.json()
        token = data.get("AccessToken", "")
        expiry_str = data.get("AccessTokenExpiration")
        if expiry_str:
            expiry = parser.isoparse(expiry_str)
        else:
            expiry = datetime.now(timezone.utc) + timedelta(minutes=30)
        access_token_data = {"token": token, "expiry": expiry}
        return token
    except Exception as e:
        print("Failed to obtain Vulcan token:", e)
        return ""

def query_vulcan(token, messages):
    url = "https://api.vulcanlabs.co/smith-v2/api/v7/chat_android"
    payload = {
        "model": "gpt-4o-mini",
        "user": DEVICE_ID,
        "messages": messages,
        "max_tokens": MAX_TOKENS,
        "nsfw_check": True,
    }
    headers = {
        "User-Agent": "Chat Smith Android, Version 4.0.5(1032)",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "x-auth-token": token,
        "authorization": f"Bearer {token}",
        "x-vulcan-application-id": "com.smartwidgetlabs.chatgpt",
        "x-vulcan-request-id": "9149487891757687028153",
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        data = response.json()
        return data["choices"][0]["Message"]["content"]
    except Exception as e:
        print("Error calling Vulcan:", e)
        return "حدث خطأ أثناء الاتصال بالنموذج."

# -----------------------------
# Helpers: Facebook send API
# -----------------------------
GRAPH_API_BASE = "https://graph.facebook.com/v17.0/me/messages"

def send_call(payload):
    if not PAGE_ACCESS_TOKEN:
        print("Missing PAGE_ACCESS_TOKEN. Cannot send:", payload)
        return
    params = {"access_token": PAGE_ACCESS_TOKEN}
    headers = {"Content-Type": "application/json"}
    r = requests.post(GRAPH_API_BASE, params=params, headers=headers, json=payload, timeout=30)
    try:
        jr = r.json()
    except Exception:
        jr = {"text": r.text}
    if r.status_code >= 400:
        print("Send API error:", r.status_code, jr)
    return jr

def send_text_message(psid, text, quick_replies=None):
    message = {"text": text}
    if quick_replies:
        message["quick_replies"] = quick_replies
    payload = {
        "recipient": {"id": psid},
        "messaging_type": "RESPONSE",
        "message": message,
    }
    return send_call(payload)

def send_buttons(psid, text, buttons):
    payload = {
        "recipient": {"id": psid},
        "messaging_type": "RESPONSE",
        "message": {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "button",
                    "text": text,
                    "buttons": buttons,
                },
            }
        },
    }
    return send_call(payload)

# Some default Arabic quick replies & buttons
def default_quick_replies():
    return [
        {"content_type": "text", "title": "مساعدة", "payload": "HELP"},
        {"content_type": "text", "title": "ابدأ محادثة جديدة", "payload": "NEW_CHAT"},
        {"content_type": "text", "title": "مثال سؤال", "payload": "EXAMPLE"},
    ]

def default_buttons():
    return [
        {"type": "postback", "title": "مساعدة", "payload": "HELP"},
        {"type": "postback", "title": "ابدأ محادثة جديدة", "payload": "NEW_CHAT"},
        # Change to your site if needed
        {"type": "web_url", "title": "زيارة الموقع", "url": "https://vercel.com/"},
    ]

# -----------------------------
# Webhook verify (GET) & receive (POST)
# -----------------------------
@app.route("/api/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Verification token mismatch", 403

@app.route("/api/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True, silent=True) or {}
    # For debugging in logs
    print("Incoming update:", json.dumps(data, ensure_ascii=False))

    if data.get("object") != "page":
        return jsonify({"status": "ignored"}), 200

    for entry in data.get("entry", []):
        for event in entry.get("messaging", []):
            sender_id = event.get("sender", {}).get("id")
            if not sender_id:
                continue

            # message (text or attachment)
            if "message" in event:
                msg = event["message"]
                if msg.get("text"):
                    handle_text(sender_id, msg["text"])
                elif msg.get("attachments"):
                    send_text_message(sender_id, "تم استلام المرفق 👌. أرسل رسالة نصية لنتابع.", default_quick_replies())
            # postback (e.g., Get Started or buttons)
            elif "postback" in event:
                payload = (event["postback"].get("payload") or "").upper()
                handle_postback(sender_id, payload)
    return jsonify({"status": "ok"}), 200

# -----------------------------
# Handlers
# -----------------------------
def handle_text(user_id, text):
    # init chat history
    if user_id not in user_chats:
        user_chats[user_id] = []

    # chat accumulation
    user_chats[user_id].append({"role": "user", "content": text})
    if len(user_chats[user_id]) > MAX_CHAT_HISTORY * 2:
        user_chats[user_id] = user_chats[user_id][-MAX_CHAT_HISTORY * 2:]

    token = get_access_token()
    if not token:
        send_text_message(user_id, "فشل الحصول على التوكن.", default_quick_replies())
        return

    reply = query_vulcan(token, user_chats[user_id])
    user_chats[user_id].append({"role": "assistant", "content": reply})

    # reply with text + quick replies
    send_text_message(user_id, reply, default_quick_replies())
    # and offer buttons
    send_buttons(user_id, "اختر إجراء:", default_buttons())

def handle_postback(user_id, payload):
    if payload == "GET_STARTED":
        send_text_message(user_id, " مرحباً! أرسل أي سؤال وسأجيب فوراً مطور البوت Aymen.B✨", default_quick_replies())
        return
    if payload == "HELP":
        send_text_message(
            user_id,
            "اكتب سؤالك مباشرة. استخدم الأزرار أدناه لبدء محادثة جديدة أو زيارة الموقع.",
            default_quick_replies(),
        )
        send_buttons(user_id, "ماذا تريد أن تفعل الآن؟", default_buttons())
        return
    if payload == "NEW_CHAT":
        user_chats[user_id] = []
        send_text_message(user_id, "بدأنا محادثة جديدة. اكتب سؤالك 🙌", default_quick_replies())
        return

    # Fallback for unknown postbacks
    send_text_message(user_id, "لم أفهم الإجراء المطلوب. جرّب كتابة سؤالك.", default_quick_replies())

# -----------------------------
# Health check
# -----------------------------
@app.route("/api/healthz", methods=["GET"])
def healthz():
    return jsonify({"ok": True, "time": datetime.utcnow().isoformat()})

# Export for Vercel (Flask is WSGI-compatible)
# app is the WSGI callable Vercel looks for.
