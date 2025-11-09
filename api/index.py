import os
import json
import requests
from datetime import datetime, timedelta, timezone
from dateutil import parser
from flask import Flask, request, jsonify

app = Flask(__name__)

# ===== إعدادات أساسية =====
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "boykta 2023")
DEVICE_ID = os.getenv("DEVICE_ID", "B4A13AE09F22A2A4")
MAX_CHAT_HISTORY = 100
MAX_TOKENS = 0

user_chats = {}
access_token_data = {"token": "", "expiry": datetime.now(timezone.utc)}

# ===== الحصول على توكن Vulcan =====
def get_access_token(force_refresh: bool = False):
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
        r = requests.post(url, json=payload, headers=headers, timeout=30)
        data = r.json()
        token = data.get("AccessToken", "")
        expiry_str = data.get("AccessTokenExpiration")
        expiry = (
            parser.isoparse(expiry_str)
            if expiry_str
            else datetime.now(timezone.utc) + timedelta(minutes=30)
        )
        access_token_data = {"token": token, "expiry": expiry}
        return token
    except Exception as e:
        print("فشل الحصول على التوكن:", e)
        return ""

# ===== إرسال واستقبال من Vulcan =====
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
        r = requests.post(url, json=payload, headers=headers, timeout=60)
        data = r.json()
        return data["choices"][0]["Message"]["content"]
    except Exception as e:
        print("خطأ في طلب Vulcan:", e)
        return "حدث خطأ أثناء الاتصال بالنموذج."

# ===== Webhook Verify =====
@app.route("/api/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "خطأ في التحقق", 403

# ===== استقبال الرسائل =====
@app.route("/api/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True) or {}
    if data.get("object") != "page":
        return jsonify({"status": "ignored"}), 200

    for entry in data.get("entry", []):
        for event in entry.get("messaging", []):
            sender = event.get("sender", {}).get("id")
            if not sender:
                continue
            if "message" in event and "text" in event["message"]:
                text = event["message"]["text"]
                handle_message(sender, text)

    return jsonify({"status": "ok"}), 200

# ===== إرسال الرسالة عبر Facebook Graph API =====
def send_message(psid, text):
    if not PAGE_ACCESS_TOKEN:
        print("تحذير: PAGE_ACCESS_TOKEN غير معيّن")
        return
    url = f"https://graph.facebook.com/v17.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {"recipient": {"id": psid}, "message": {"text": text}}
    headers = {"Content-Type": "application/json"}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        print("إرسال:", r.status_code, r.text)
    except Exception as e:
        print("فشل الإرسال:", e)

# ===== الرد على المستخدم =====
def handle_message(user_id, text):
    msg = (text or "").strip().lower()

    # --- ردود مخصّصة ---
    # مطورك / من مطورك / من أنشئك / من صنعك
    if ("مطورك" in msg) or ("من مطورك" in msg) or ("من أنشئك" in msg) or ("من صنعك" in msg):
        send_message(
            user_id,
            "مطوري هو aymen bourai مبرمج كبير لكن ابقا مجرد ذكاء اصطناعي مساعد له"
        )
        return

    # سلام / السلام عليكم
    if msg == "سلام" or msg.startswith("سلام") or ("السلام عليكم" in msg):
        send_message(user_id, "وعليكم السلام ورحمة الله وبركاته")
        send_message(user_id, "أنا ذكاء اصطناعي")
        return

    # لو كتب المستخدم "وعليكم السلام" مباشرة
    if "وعليكم السلام" in msg:
        send_message(user_id, "أنا ذكاء اصطناعي")
        return

    # --- المنطق الافتراضي: محادثة مع النموذج ---
    if user_id not in user_chats:
        user_chats[user_id] = []

    user_chats[user_id].append({"role": "user", "content": text})
    if len(user_chats[user_id]) > MAX_CHAT_HISTORY * 2:
        user_chats[user_id] = user_chats[user_id][-MAX_CHAT_HISTORY * 2:]

    token = get_access_token()
    if not token:
        send_message(user_id, "⚠️ فشل الحصول على التوكن.")
        return

    reply = query_vulcan(token, user_chats[user_id])
    user_chats[user_id].append({"role": "assistant", "content": reply})
    send_message(user_id, reply)

@app.route("/api/healthz")
def healthz():
    return jsonify({"ok": True})

# ========== نهاية ==========
