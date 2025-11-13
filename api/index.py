import requests
from datetime import datetime, timedelta, timezone
from dateutil import parser
from flask import Flask, request, jsonify

app = Flask(__name__)

VERIFY_TOKEN = "boykta 2023"      # توكن تأكيد الويبهوك
PAGE_ACCESS_TOKEN = "ضع_توكن_صفحتك_هنا"

DEVICE_ID = "B4A13AE09F22A2A4"

MAX_CHAT_HISTORY = 60
user_chats = {}

access_token_data = {"token": "", "expiry": datetime.now(timezone.utc)}

# ------------------ Vulcan Auth ------------------
def get_access_token(force_refresh=False):
    global access_token_data
    if not force_refresh and access_token_data["token"] and access_token_data["expiry"] > datetime.now(timezone.utc):
        return access_token_data["token"]

    url = "https://api.vulcanlabs.co/smith-auth/api/v1/token"
    payload = {
        "device_id": DEVICE_ID,
        "order_id": "",
        "product_id": "",
        "purchase_token": "",
        "subscription_id": ""
    }
    headers = {
        "User-Agent": "Chat Smith Android, Version 4.0.5(1032)",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "x-vulcan-application-id": "com.smartwidgetlabs.chatgpt",
        "x-vulcan-request-id": "9149487891757687027212"
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        data = response.json()
        token = data.get("AccessToken", "")
        expiry = parser.isoparse(data.get("AccessTokenExpiration"))
        access_token_data = {"token": token, "expiry": expiry}
        return token
    except:
        return ""

# ------------------ Vulcan Query ------------------
def ask_vulcan(messages):
    token = get_access_token()
    if not token:
        return "لم أستطع الوصول إلى النظام حالياً."

    url = "https://api.vulcanlabs.co/smith-v2/api/v7/chat_android"
    payload = {
        "model": "gpt-4o-mini",
        "user": DEVICE_ID,
        "messages": messages,
        "max_tokens": 0
    }
    headers = {
        "User-Agent": "Chat Smith Android, Version 4.0.5(1032)",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "authorization": f"Bearer {token}"
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        data = response.json()
        msg = data["choices"][0]["Message"]["content"]
        return msg
    except:
        return "حدث خطأ في المعالجة."

# ------------------ Facebook Send API ------------------
def send_message(user_id, text):
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {
        "recipient": {"id": user_id},
        "message": {
            "text": text,
            "quick_replies": [
                {
                    "content_type": "text",
                    "title": "المطور",
                    "payload": "DEV_BTN"
                }
            ]
        }
    }
    requests.post(url, json=payload)

# ------------------ Webhook Verification ------------------
@app.route("/", methods=["GET"])
def verify():
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge")
    return "Invalid token"

# ------------------ Receive Messages ------------------
@app.route("/", methods=["POST"])
def webhook():
    data = request.json

    for
