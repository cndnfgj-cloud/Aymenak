import json
import requests
from datetime import datetime, timezone
from dateutil import parser

VERIFY_TOKEN = "boykta 2023"
PAGE_ACCESS_TOKEN = "ضع_توكن_صفحتك_هنا"
DEVICE_ID = "B4A13AE09F22A2A4"

MAX_CHAT_HISTORY = 60
user_chats = {}

access_token_data = {"token": "", "expiry": datetime.now(timezone.utc)}

# ----------------------------------------------------
# الحصول على توكن Vulcan
# ----------------------------------------------------
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
        "User-Agent": "Chat Smith Android",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "x-vulcan-application-id": "com.smartwidgetlabs.chatgpt"
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


# ----------------------------------------------------
# إرسال رسالة لفيسبوك
# ----------------------------------------------------
def send_message(recipient_id, text):
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {
        "recipient": {"id": recipient_id},
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


# ----------------------------------------------------
# استعلام Vulcan
# ----------------------------------------------------
def ask_vulcan(messages):
    token = get_access_token()
    if not token:
        return "لا يمكن الوصول للنظام الآن."

    url = "https://api.vulcanlabs.co/smith-v2/api/v7/chat_android"
    payload = {
        "model": "gpt-4o-mini",
        "user": DEVICE_ID,
        "messages": messages,
        "max_tokens": 0
    }
    headers = {
        "User-Agent": "Chat Smith Android",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "authorization": f"Bearer {token}"
    }

    try:
        resp = requests.post(url, json=payload, headers=headers)
        data = resp.json()
        msg = data["choices"][0]["Message"]["content"]
        msg = msg.replace("T_R_X_AI", "").strip()
        return msg
    except:
        return "حدث خطأ."


# ----------------------------------------------------
# Webhook Handler
# ----------------------------------------------------
def handler(request, response):
    if request.method == "GET":
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return response.send(request.args.get("hub.challenge"))
        return response.send("TOKEN ERROR")

    if request.method == "POST":
        data = request.json

        for entry in data.get("entry", []):
            for event in entry.get("messaging", []):

                if "message" in event:
                    user_id = event["sender"]["id"]
                    text = event["message"].get("text", "").strip()

                    # زر المطور
                    if text == "المطور":
                        send_message(user_id, "حساب مطوري:\nhttps://www.facebook.com/aymen.bourai.2025")
                        return response.send("ok")

                    # تعريف المطور
                    if "aymen bourai" in text.lower():
                        send_message(
                            user_id,
                            "نعم، aymen bourai هو مطوري. شاب من مواليد 2007 يحب البرمجة والعزلة وأتمنى له مستقبلاً رائعاً."
                        )
                        return response.send("ok")

                    # حفظ المحادثة
                    if user_id not in user_chats:
                        user_chats[user_id] = []

                    user_chats[user_id].append({"role": "user", "content": text})

                    if len(user_chats[user_id]) > MAX_CHAT_HISTORY:
                        user_chats[user_id] = user_chats[user_id][-MAX_CHAT_HISTORY:]

                    reply = ask_vulcan(user_chats[user_id])

                    user_chats[user_id].append({"role": "assistant", "content": reply})

                    send_message(user_id, reply)

        return response.send("ok")

    return response.send("METHOD NOT ALLOWED")
