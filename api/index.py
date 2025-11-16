from flask import Flask, request, jsonify
import os
import requests

app = Flask(__name__)

# متغيرات البيئة
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN", "")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "boykta2023")

# نصوص خاصة بالمطور
AYMEN_PROFILE_TEXT = (
    "نعم aymen bourai هو مطوري عمره 18 سنة من مواليد 2007 "
    "شخص شاب مبرمج لتطبيقات ومواقع يحب البرمجة واتمنى له مستقبل باهر "
    "من ناحية الدراسة لاأعلم عن هذا امر لكنه شخص انطوائي يحب العزلة."
)
DEVELOPER_TEXT = "aymen bourai هو مطوري وانا مطيع له وابقا مساعد له."

GRAPH_API_URL = "https://graph.facebook.com/v16.0/me/messages"

# دالة إرسال الرسائل
def send_message(psid, text):
    payload = {"recipient": {"id": psid}, "message": {"text": text}}
    try:
        requests.post(
            GRAPH_API_URL,
            params={"access_token": PAGE_ACCESS_TOKEN},
            json=payload,
            timeout=10
        )
    except Exception as e:
        print("Send message error:", e)

# Webhook verification
@app.route("/api/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Verification token mismatch", 403

# Webhook للرسائل
@app.route("/api/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    if data is None:
        return "No payload", 400

    for entry in data.get("entry", []):
        for messaging in entry.get("messaging", []):
            sender_psid = messaging.get("sender", {}).get("id")
            if not sender_psid:
                continue

            # الرد على زر Get Started أو أي postback
            if messaging.get("postback"):
                payload = messaging["postback"].get("payload")
                if payload == "GET_STARTED_PAYLOAD":
                    send_message(sender_psid, "أهلاً! أرسل لي أي رسالة وسأرد عليك مباشرة.")
                    continue

            # الرد على الرسائل النصية
            if messaging.get("message"):
                text = messaging["message"].get("text", "").strip()
                lowered = text.lower()

                # ردود خاصة على المطور
                special_keywords = ["aymen bourai", "aymen", 
                                    "من قام بإنتاجك", "من مطورك", "من أسسك",
                                    "من مصممك", "من صنعك"]
                if any(word in lowered for word in special_keywords):
                    if "aymen bourai" in lowered or "aymen" in lowered:
                        send_message(sender_psid, AYMEN_PROFILE_TEXT)
                    else:
                        send_message(sender_psid, DEVELOPER_TEXT)
                    continue

                # استعلام API الخارجي
                try:
                    r = requests.get(
                        f"https://vetrex.x10.mx/api/gpt4.php?text={text}",
                        timeout=10
                    )
                    data = r.json()  # تحويل الاستجابة إلى JSON
                    reply = data.get("answer", "انا لا أدعم قرائة ماذا يوجد في صورة نعتذر لذلك سيحاول المطور حل ذلك قريبااا.🫶").strip()
                except Exception:
                    reply = "عذراً، الخدمة غير متاحة حالياً."

                send_message(sender_psid, reply)

    return "EVENT_RECEIVED", 200

# Endpoint صحيّة للتأكد من عمل السيرفر
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(debug=True, port=3000)
