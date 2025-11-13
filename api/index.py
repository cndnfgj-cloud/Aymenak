# facebook_bot_webhook.py
# Vercel Python Serverless Function
# Requirements: flask, requests

from flask import Flask, request
import requests

app = Flask(__name__)

VERIFY_TOKEN = "boykta2023"  # verify token
PAGE_ACCESS_TOKEN = "YOUR_PAGE_ACCESS_TOKEN"  # ضع توكن صفحتك هنا

# إرسال رسالة للمستخدم
def send_message(recipient_id, text):
    url = "https://graph.facebook.com/v17.0/me/messages"
    params = {"access_token": PAGE_ACCESS_TOKEN}
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text}
    }
    requests.post(url, params=params, json=payload)

# تأكيد Webhook
@app.route('/api/webhook', methods=['GET'])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Verification failed", 403

# استقبال رسائل المستخدمين
@app.route('/api/webhook', methods=['POST'])
def webhook():
    data = request.get_json()

    if data.get("object") == "page":
        for entry in data.get("entry", []):
            for messaging in entry.get("messaging", []):
                sender_id = messaging["sender"]["id"]

                if "message" in messaging:
                    text = messaging["message"].get("text", "").strip().lower()

                    # رد خاص باسم مطور البوت
                    if text == "aymen bourai":
                        response = (
                            "نعم aymen bourai هو مطوري عمره 18 سنة من مواليد 2007، "
                            "شخص شاب مبرمج لتطبيقات ومواقع يحب البرمجة واتمنى له مستقبل باهر. "
                            "من ناحية الدراسة لا أعلم عن هذا الأمر لكنه شخص انطوائي يحب العزلة."
                        )
                        send_message(sender_id, response)
                        continue

                    # استدعاء API الخارجي
                    r = requests.get(f"https://vetrex.x10.mx/api/gpt4.php?text={text}")
                    reply = r.text.strip()

                    # إضافة تعريف البوت بمطوره
                    final_reply = reply + "\nتم انتاجي من طرف aymen bourai وانا مطيع له وابقى مساعد له"

                    send_message(sender_id, final_reply)

    return "OK", 200

# Handler خاص بـ Vercel
def handler(request):
    with app.app_context():
        return app.full_dispatch_request()
