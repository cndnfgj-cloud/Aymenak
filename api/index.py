# facebook_bot_webhook.py
# Vercel Python Serverless Function
# Requirements: flask, requests

from flask import Flask, request
import requests
import json

app = Flask(__name__)

# تأكد أن هذا هو نفس التوكن الذي وضعته في إعدادات فيسبوك
VERIFY_TOKEN = "boykta 2023"
# ضع هنا توكن صفحة الفيسبوك الخاصة بالبوت
PAGE_ACCESS_TOKEN = "YOUR_PAGE_ACCESS_TOKEN"

FACEBOOK_API_URL = "https://graph.facebook.com/v17.0/me/messages"


def send_message(recipient_id, text):
    """
    يرسل رسالة نصية عادية بدون أزرار للمستخدم
    """
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text}
    }
    params = {"access_token": PAGE_ACCESS_TOKEN}
    requests.post(FACEBOOK_API_URL, params=params, json=payload)


def send_message_with_quick_replies(recipient_id, text):
    """
    مثال على إرسال رسالة مع أزرار (Quick Replies)
    هذه الدالة غير مستخدمة افتراضياً، لكن جاهزة لك لو حاب تفعل الأزرار لاحقاً.
    """
    payload = {
        "recipient": {"id": recipient_id},
        "message": {
            "text": text,
            "quick_replies": [
                {
                    "content_type": "text",
                    "title": "من هو مطورك؟",
                    "payload": "DEV_INFO"
                },
                {
                    "content_type": "text",
                    "title": "تواصل مع المطور",
                    "payload": "CONTACT_DEV"
                },
                {
                    "content_type": "text",
                    "title": "معلومات عنك",
                    "payload": "BOT_INFO"
                }
            ]
        }
    }
    params = {"access_token": PAGE_ACCESS_TOKEN}
    requests.post(FACEBOOK_API_URL, params=params, json=payload)


def clean_reply(raw_text: str) -> str:
    """
    تنظيف الرد القادم من الـ API:
    - محاولة قراءة JSON إن وجد
    - إزالة الكلمات: data, answer, dev
    - إزالة كل علامات التنصيص ""
    - إرجاع جملة نظيفة فقط
    """
    if not raw_text:
        return ""

    raw_text = raw_text.strip()

    # محاولة تفسير الاستجابة كـ JSON
    try:
        data = json.loads(raw_text)

        # لو كانت الاستجابة dict نحاول نأخذ الحقل المنطقي
        if isinstance(data, dict):
            for key in ["answer", "data", "dev", "msg", "message", "text"]:
                if key in data and isinstance(data[key], str):
                    raw_text = data[key]
                    break
            else:
                # لو ما وجدنا مفتاح مناسب، نجمع كل القيم النصية
                raw_text = " ".join(
                    str(v) for v in data.values() if isinstance(v, str)
                )

        # لو كانت الاستجابة list نجمع العناصر
        elif isinstance(data, list):
            raw_text = " ".join(str(item) for item in data)

    except Exception:
        # لو ليست JSON نخليها كما هي
        pass

    # إزالة الكلمات المطلوبة
    for word in ["data", "answer", "dev"]:
        raw_text = raw_text.replace(word, "")

    # إزالة علامات التنصيص
    raw_text = raw_text.replace('"', "").replace("'", "")

    # تنظيف المسافات الزائدة
    raw_text = raw_text.strip()

    return raw_text


# Webhook Verification
@app.route("/api/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200

    return "Verification failed", 403


# Webhook Receive Messages
@app.route("/api/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    if data.get("object") == "page":
        for entry in data.get("entry", []):
            for messaging in entry.get("messaging", []):
                sender_id = messaging["sender"]["id"]

                if "message" in messaging:
                    original_text = messaging["message"].get("text", "") or ""
                    cleaned_text = original_text.strip()
                    lowered = cleaned_text.lower()

                    # رد خاص باسم المطور
                    if lowered == "aymen bourai":
                        response = (
                            "نعم aymen bourai هو مطوري عمره 18 سنة من مواليد 2007، "
                            "شخص شاب مبرمج لتطبيقات ومواقع يحب البرمجة وأتمنى له مستقبل باهر. "
                            "من ناحية الدراسة لا أعلم عن هذا الأمر، "
                            "لكنه شخص انطوائي يحب العزلة."
                        )
                        send_message(sender_id, response)
                        continue

                    # استدعاء API الخارجي
                    try:
                        api_response = requests.get(
                            "https://vetrex.x10.mx/api/gpt4.php",
                            params={"text": cleaned_text},
                            timeout=30
                        )
                        raw_reply = api_response.text
                    except Exception:
                        raw_reply = "حدث خطأ في الاتصال بالخادم الخارجي."

                    # تنظيف الرد
                    reply_body = clean_reply(raw_reply)

                    # إضافة تعريف البوت بمطوره
                    final_reply = (
                        reply_body
                        + "\nتم انتاجي من طرف aymen bourai وانا مطيع له وابقى مساعد له"
                    )

                    # هنا نستخدم رسالة نصية فقط بدون أزرار كما طلبت
                    send_message(sender_id, final_reply)

    return "OK", 200
