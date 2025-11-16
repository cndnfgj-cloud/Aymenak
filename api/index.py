from flask import Flask, request, jsonify
import requests
import json

app = Flask(__name__)

VERIFY_TOKEN = "boykta_2023"
PAGE_ACCESS_TOKEN = "PUT_YOUR_PAGE_ACCESS_TOKEN_HERE"

API_URL = "https://vetrex.x10.mx/api/gpt4.php?text="


def send_message(psid, text):
    url = f"https://graph.facebook.com/v17.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {
        "recipient": {"id": psid},
        "message": {"text": text}
    }
    requests.post(url, json=payload)


@app.route("/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    challenge = request.args.get("hub.challenge")
    token = request.args.get("hub.verify_token")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200

    return "Verification token mismatch", 403


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    if data["object"] == "page":
        for entry in data["entry"]:
            for messaging in entry.get("messaging", []):

                sender = messaging["sender"]["id"]

                # 1 — رد عند إرسال صورة
                if "attachments" in messaging.get("message", {}):
                    send_message(sender, "✨ انا اسف لا أعدم رؤية صور او انشاء صور المطور aymen يعمل على هذت مشكل وسيتم حل مشكلة قريبا")
                    continue

                # 2 — رد عند إرسال زر إعجاب 👍 (reaction)
                if "reaction" in messaging:
                    send_message(sender, "👋 أهلاً! يمكنك سؤالي أي شيء وأنا جاهز دائماً.")
                    continue

                # 3 — نص المستخدم
                if "text" not in messaging["message"]:
                    continue

                text = messaging["message"]["text"].strip().lower()

                # ردود خاصة عن مطورك
                if any(kw in text for kw in ["من قام بإنتاجك", "من مطورك", "من انتجك", "من صنعك", "من أسسك", "من مصممك"]):
                    send_message(sender, "❤️ aymen bourai هو مطوري، وأنا مطيع له دائماً وباقٍ كمساعد له.")
                    continue

                # معلومات إضافية عن أيمن
                if "aymen bourai" in text or "aymen" in text:
                    send_message(sender,
                        "نعم، aymen bourai هو مطوري.\n"
                        "عمره 18 سنة من مواليد 2007.\n"
                        "مبرمج مواقع وتطبيقات، يحب البرمجة كثيراً.\n"
                        "أتمنى له مستقبلاً رائعاً.\n"
                        "من ناحية الدراسة لا أعلم، لكنه شخص انطوائي ويحب العزلة."
                    )
                    continue

                # طلب من API — رد نصي فقط
                try:
                    r = requests.get(API_URL + text, timeout=10)
                    j = r.json()

                    # استخراج answer فقط
                    answer = j.get("answer", "لم أستطع فهم الإجابة من الخادم.")

                except Exception:
                    answer = "⚠ حدث خطأ أثناء الاتصال بالخادم."

                send_message(sender, answer)

    return "EVENT_RECEIVED", 200


@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "bot running"}), 200
