# api/webhook.py
from flask import Flask, request, jsonify
import os
import requests
import threading
from datetime import datetime, timedelta, timezone
from dateutil import parser

app = Flask(__name__)

# === إعداد المتغيرات من بيئة Vercel ===
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN", "")  # ضع هنا توكن الصفحة
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "verify_me_123")  # اختر قيمة خاصة بك
DEVICE_ID = os.environ.get("DEVICE_ID", "B4A13AE09F22A2A4")

# === إعدادات Vulcan (نسخة معدلة من كودك) ===
access_token_data = {"token": "", "expiry": datetime.now(timezone.utc)}

def get_access_token(force_refresh=False):
    global access_token_data
    if not force_refresh and access_token_data["token"] and access_token_data["expiry"] > datetime.now(timezone.utc):
        return access_token_data["token"]

    url = "https://api.vulcanlabs.co/smith-auth/api/v1/token"
    payload = {"device_id": DEVICE_ID, "order_id": "", "product_id": "", "purchase_token": "", "subscription_id": ""}
    headers = {
        "User-Agent": "Chat Smith Android, Version 4.0.5(1032)",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "x-vulcan-application-id": "com.smartwidgetlabs.chatgpt",
        "x-vulcan-request-id": "9149487891757687027212"
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=20)
        data = r.json()
        token = data.get("AccessToken", "")
        expiry_str = data.get("AccessTokenExpiration")
        if expiry_str:
            expiry = parser.isoparse(expiry_str)
        else:
            expiry = datetime.now(timezone.utc) + timedelta(minutes=30)
        access_token_data.update({"token": token, "expiry": expiry})
        return token
    except Exception as e:
        print("فشل الحصول على التوكن من Vulcan:", e)
        return ""

def query_vulcan(token, messages, max_tokens=0):
    url = "https://api.vulcanlabs.co/smith-v2/api/v7/chat_android"
    payload = {
        "model": "gpt-4o-mini",
        "user": DEVICE_ID,
        "messages": messages,
        "max_tokens": max_tokens,
        "nsfw_check": True
    }
    headers = {
        "User-Agent": "Chat Smith Android, Version 4.0.5(1032)",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "x-auth-token": token,
        "authorization": f"Bearer {token}",
        "x-vulcan-application-id": "com.smartwidgetlabs.chatgpt",
        "x-vulcan-request-id": "9149487891757687028153"
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=30)
        data = r.json()
        return data["choices"][0]["Message"]["content"]
    except Exception as e:
        print("خطأ في طلب Vulcan:", e)
        return "حدث خطأ أثناء الاتصال بالنموذج."

# === تخزين محادثات المستخدمين (in-memory) ===
user_chats = {}
MAX_CHAT_HISTORY = 100

# === وظائف إرسال رسائل لمسنجر ===
GRAPH_API_URL = "https://graph.facebook.com/v16.0/me/messages"

def send_message(psid, text, quick_replies=None, buttons=None):
    """إرسال رسالة نصية مع خيارات سريعة أو أزرار قالب"""
    payload = {
        "recipient": {"id": psid},
        "message": {}
    }
    if buttons:
        # استخدم قالب زر إذا طُلب
        payload["message"] = {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "button",
                    "text": text,
                    "buttons": buttons
                }
            }
        }
    elif quick_replies:
        payload["message"] = {
            "text": text,
            "quick_replies": quick_replies
        }
    else:
        payload["message"] = {"text": text}

    params = {"access_token": PAGE_ACCESS_TOKEN}
    try:
        r = requests.post(GRAPH_API_URL, params=params, json=payload, timeout=20)
        return r.status_code, r.text
    except Exception as e:
        print("خطأ في send_message:", e)
        return None, str(e)

# === تجهيز ملف ملف التعريف (Get Started + Persistent Menu) ===
def set_messenger_profile():
    if not PAGE_ACCESS_TOKEN:
        print("لم يتم ضبط PAGE_ACCESS_TOKEN. تجاوز إعداد ملف الماسنجر.")
        return
    profile_url = f"https://graph.facebook.com/v16.0/me/messenger_profile"
    payload = {
        "get_started": {"payload": "GET_STARTED_PAYLOAD"},
        "persistent_menu": [
            {
                "locale": "default",
                "composer_input_disabled": False,
                "call_to_actions": [
                    {"type": "postback", "title": "مساعدة", "payload": "HELP_PAYLOAD"},
                    {"type": "postback", "title": "اتصل بالمطور", "payload": "CONTACT_DEV_PAYLOAD"},
                    {"type": "web_url", "title": "موقعي", "url": "https://example.com", "webview_height_ratio": "full"}
                ]
            }
        ]
    }
    params = {"access_token": PAGE_ACCESS_TOKEN}
    try:
        r = requests.post(profile_url, params=params, json=payload, timeout=10)
        print("set_messenger_profile:", r.status_code, r.text)
    except Exception as e:
        print("خطأ ضبط ملف الماسنجر:", e)

# شغّل مرة عند البداية لضبط Get Started و persistent menu
try:
    threading.Thread(target=set_messenger_profile).start()
except Exception as e:
    print("خطأ في بدء thread لضبط الملف:", e)

# === معالجة نصوص خاصة بالـ developer كما طلبت ===
DEVELOPER_TEXT = (
    "من قام بإنتاجي يقول aymen bourai هو مطوري وانا مطيع له وابقا مساعد له."
)
AYMEN_PROFILE_TEXT = (
    "نعم aymen bourai هو مطوري. عمره 18 سنة (مواليد 2007). "
    "شخص شاب مبرمج تطبيقات ومواقع، يحب البرمجة ويتمنى مستقبل باهر. "
    "من ناحية الدراسة لست متأكداً لكن هو شخص انطوائي ويحب العزلة."
)

# === webhook verification (GET) ===
@app.route("/api/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Verification token mismatch", 403

# === webhook للرسائل (POST) ===
@app.route("/api/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    # Facebook may send many entries
    if data is None:
        return "No payload", 400

    for entry in data.get("entry", []):
        for messaging in entry.get("messaging", []):
            sender_psid = messaging.get("sender", {}).get("id")
            if not sender_psid:
                continue

            # حدث: خلال الضغط على Get Started أو قوائم postback
            if messaging.get("postback"):
                payload = messaging["postback"].get("payload")
                if payload == "GET_STARTED_PAYLOAD":
                    # افتح محادثة جديدة للمستخدم
                    user_chats[sender_psid] = []
                    # رد ترحيبي مع أزرار
                    buttons = [
                        {"type": "postback", "title": "اطرح سؤال", "payload": "ASK_PAYLOAD"},
                        {"type": "postback", "title": "معلومات عن المطور", "payload": "DEV_PAYLOAD"}
                    ]
                    send_message(sender_psid, "أهلاً! أرسل سؤالك هنا أو اختر زرًا:", buttons=buttons)
                    # أضف نص المطور كبادئ
                    send_message(sender_psid, DEVELOPER_TEXT)
                elif payload == "HELP_PAYLOAD":
                    send_message(sender_psid, "كيف أساعدك؟ أرسل سؤالك مباشرة.")
                elif payload == "CONTACT_DEV_PAYLOAD" or payload == "DEV_PAYLOAD":
                    send_message(sender_psid, AYMEN_PROFILE_TEXT)
                elif payload == "ASK_PAYLOAD":
                    send_message(sender_psid, "أرسل لي سؤالك أو وصف المشكلة وسأجيب فورًا.")
                else:
                    send_message(sender_psid, "تم استلام الطلب: " + str(payload))
                continue

            # حدث: رسالة نصية عادية
            if messaging.get("message"):
                message = messaging["message"]
                text = message.get("text", "").strip()
                # ردود فورية للعبارات الخاصة
                lowered = text.lower()
                if "aymen bourai" in lowered or "aymen" in lowered:
                    send_message(sender_psid, AYMEN_PROFILE_TEXT)
                    continue
                if "من قام بإنتاجك" in text or "من قام بإنتاجي" in text or "من قام بإنتاجك" in text:
                    send_message(sender_psid, DEVELOPER_TEXT)
                    continue

                # تعامل مع الحوار عبر Vulcan (سجل التاريخ مشابه للتيليجرام)
                if sender_psid not in user_chats:
                    user_chats[sender_psid] = []

                user_chats[sender_psid].append({"role": "user", "content": text})
                # قص المحادثة لو زاد الحد
                if len(user_chats[sender_psid]) > MAX_CHAT_HISTORY * 2:
                    user_chats[sender_psid"] = user_chats[sender_psid][-MAX_CHAT_HISTORY*2:]

                # أرسل مؤشر كتابة (اختياري) عبر API (typing_on)
                try:
                    typing_payload = {
                        "recipient": {"id": sender_psid},
                        "sender_action": "typing_on"
                    }
                    requests.post(GRAPH_API_URL, params={"access_token": PAGE_ACCESS_TOKEN}, json=typing_payload, timeout=5)
                except Exception:
                    pass

                # استعلام Vulcan بشكل متزامن (قد يأخذ بضع ثواني)
                token = get_access_token()
                if not token:
                    send_message(sender_psid, "فشل الحصول على التوكن من الخادم. حاول لاحقاً.")
                    continue

                try:
                    reply = query_vulcan(token, user_chats[sender_psid])
                except Exception:
                    reply = "عذراً، حدث خطأ أثناء توليد الرد."

                user_chats[sender_psid].append({"role": "assistant", "content": reply})

                # إرجاع أزرار سريعة مع الرد
                quick = [
                    {"content_type": "text", "title": "سؤال آخر", "payload": "ASK_MORE"},
                    {"content_type": "text", "title": "معلومات عن المطور", "payload": "DEV_PAYLOAD"}
                ]
                send_message(sender_psid, reply, quick_replies=quick)
    return "EVENT_RECEIVED", 200

# Endpoint بسيط للتأكد من أن السيرفر يعمل
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200

# لازم لعمل run محلي (Vercel لا يستخدم هذا الجزء عادةً)
if __name__ == "__main__":
    app.run(debug=True, port=3000)
