from flask import Flask, request
import requests
import json

app = Flask(__name__)

VERIFY_TOKEN = "boykta 2023"
PAGE_ACCESS_TOKEN = "YOUR_PAGE_ACCESS_TOKEN"  # ضع توكن صفحتك هنا

FACEBOOK_API_URL = "https://graph.facebook.com/v17.0/me/messages"


def send_message(recipient_id, text):
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text}
    }
    params = {"access_token": PAGE_ACCESS_TOKEN}
    requests.post(FACEBOOK_API_URL, params=params, json=payload)


def clean_reply(raw_text: str) -> str:
    if not raw_text:
        return ""

    raw_text = raw_text.strip()

    try:
        data = json.loads(raw_text)

        if isinstance(data, dict):
            for key in ["answer", "data", "dev", "msg", "message", "text"]:
                if key in data and isinstance(data[key], str):
                    raw_text = data[key]
                    break
            else:
                raw_text = " ".join(
                    str(v) for v in data.values() if isinstance(v, str)
                )

        elif isinstance(data, list):
            raw_text = " ".join(str(item) for item in data)

    except Exception:
        pass

    for word in ["data", "answer", "dev"]:
        raw_text = raw_text.replace(word, "")

    raw_text = raw_text.replace('"', "").replace("'", "")
    raw_text = raw_text.strip()

    return raw_text


@app.route("/api/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200

    return "Verification failed", 403


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

                    if lowered == "aymen bourai":
                        response = (
                            "نعم aymen bourai هو مطوري عمره 18 سنة من مواليد 2007، "
                            "شخص شاب مبرمج لتطبيقات ومواقع يحب البرمجة وأتمنى له مستقبل باهر. "
                            "من ناحية الدراسة لا أعلم عن هذا الأمر، "
                            "لكنه شخص انطوائي يحب العزلة."
                        )
                        send_message(sender_id, response)
                        continue

                    try:
                        api_response = requests.get(
                            "https://vetrex.x10.mx/api/gpt4.php",
                            params={"text": cleaned_text},
                            timeout=30
                        )
                        raw_reply = api_response.text
                    except Exception:
                        raw_reply = "حدث خطأ في الاتصال بالخادم الخارجي."

                    reply_body = clean_reply(raw_reply)

                    final_reply = (
                        reply_body
                        + "\nتم انتاجي من طرف aymen bourai وانا مطيع له وابقى مساعد له"
                    )

                    send_message(sender_id, final_reply)

    return "OK", 200
