from flask import Flask, request, jsonify
import os
import requests
import time

app = Flask(__name__)

# مفاتيح البيئة
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN", "")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "boykta2023")

# روابط APIs
GPT_API_BASE = "https://vetrex.x10.mx/api/gpt4.php?text="
IMAGE_API_BASE = "https://sii3.top/api/imagen-3.php?aspect_ratio=1:1&style=Auto&text="
GRAPH_API_URL = "https://graph.facebook.com/v17.0/me/messages"

# حالات انتظار وصف الصورة
awaiting_image = {}  # {psid: timestamp}

# نصوص خاصة بالمطور
DEVELOPER_TEXT = (
    "مطور البوت aymen bourai طورني لمساعدة أشخاص قانونياً، "
    "لكني أظل مجرد مساعد له وأسعى لمساعدة الناس من خلاله."
)
AYMEN_PROFILE_TEXT = (
    "نعم aymen bourai هو مطوري.\n"
    "عمره 18 سنة من مواليد 2007.\n"
    "شخص شاب مبرمج لتطبيقات ومواقع ويحب البرمجة.\n"
    "أتمنى له مستقبل باهر.\n"
    "لكن من ناحية الدراسة لا أعلم، هو أمر يخصه.\n"
    "شخص انطوائي ويحب العزلة."
)

# دوال مساعدة
def send_message(psid, text):
    payload = {"recipient": {"id": psid}, "message": {"text": text}}
    try:
        requests.post(GRAPH_API_URL, params={"access_token": PAGE_ACCESS_TOKEN}, json=payload, timeout=10)
    except Exception as e:
        print("Send message error:", e)

def send_image(psid, image_url):
    payload = {
        "recipient": {"id": psid},
        "message": {"attachment": {"type": "image", "payload": {"url": image_url, "is_reusable": True}}}
    }
    try:
        requests.post(GRAPH_API_URL, params={"access_token": PAGE_ACCESS_TOKEN}, json=payload, timeout=10)
    except Exception as e:
        print("Send image error:", e)

def send_button_template(psid, text, buttons):
    payload = {
        "recipient": {"id": psid},
        "message": {
            "attachment": {
                "type": "template",
                "payload": {"template_type": "button", "text": text, "buttons": buttons}
            }
        }
    }
    try:
        requests.post(GRAPH_API_URL, params={"access_token": PAGE_ACCESS_TOKEN}, json=payload, timeout=10)
    except Exception as e:
        print("Send button error:", e)

# Webhook verification
@app.route("/api/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Verification token mismatch", 403

# Webhook POST
@app.route("/api/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True)
    if not data or data.get("object") != "page":
        return "Ignored", 200

    for entry in data.get("entry", []):
        for messaging in entry.get("messaging", []):
            psid = messaging.get("sender", {}).get("id")
            if not psid:
                continue

            # التعامل مع postback
            if messaging.get("postback"):
                payload = messaging["postback"].get("payload", "")
                if payload == "GET_STARTED_PAYLOAD":
                    buttons = [
                        {"type": "postback", "title": "إنشاء صورة", "payload": "CREATE_IMAGE_PAYLOAD"},
                        {"type": "postback", "title": "اسأل نص", "payload": "ASK_TEXT_PAYLOAD"}
                    ]
                    send_button_template(psid, "أهلاً! اختر ما تريد أو أرسل نصاً:", buttons)
                    continue
                if payload == "CREATE_IMAGE_PAYLOAD":
                    awaiting_image[psid] = time.time()
                    send_message(psid, "حسناً، أرسل وصف الصورة التي تريد إنشاؤها الآن.")
                    continue
                if payload == "ASK_TEXT_PAYLOAD":
                    send_message(psid, "أرسل أي نص لأجيبك مباشرة.")
                    continue

            # التعامل مع الرسائل النصية
            message = messaging.get("message", {})
            text = message.get("text", "").strip() if message else ""
            if not text:
                continue
            text_lower = text.lower()

            # الرد على أسئلة المطور
            dev_keywords = [
                "من مطورك", "من انتجك", "من صنع البوت",
                "من انتج البوت", "من انشئك", "من اخترعك", "من انتجك"
            ]
            if any(kw in text_lower for kw in dev_keywords):
                send_message(psid, DEVELOPER_TEXT)
                continue

            # الرد عند ذكر أيمن
            if "aymen bourai" in text_lower or "aymen" in text_lower:
                send_message(psid, AYMEN_PROFILE_TEXT)
                continue

            # إذا المستخدم في وضع انتظار وصف الصورة
            if psid in awaiting_image:
                awaiting_image.pop(psid, None)
                send_message(psid, "جارٍ إنشاء الصورة، انتظر لحظة...")
                try:
                    prompt = requests.utils.requote_uri(text)
                    r = requests.get(IMAGE_API_BASE + prompt, timeout=15).json()
                    image_url = r.get("image")
                    if image_url:
                        send_image(psid, image_url)
                    else:
                        send_message(psid, "لم أتمكن من إنشاء الصورة. حاول وصفًا مختلفًا.")
                except Exception as e:
                    print("Image API error:", e)
                    send_message(psid, "حدث خطأ أثناء الاتصال بخدمة إنشاء الصور.")
                continue

            # الرد على نص المستخدم عبر GPT API
            try:
                query = requests.utils.requote_uri(text)
                r = requests.get(GPT_API_BASE + query, timeout=10)
                j = r.json()
                ans = j.get("answer", "عذرًا، لم يصلني جواب واضح.").strip()
            except Exception:
                ans = "⚠ الخدمة غير متاحة حالياً."
            send_message(psid, ans)

    return "EVENT_RECEIVED", 200

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "bot running"}), 200

if __name__ == "__main__":
    app.run(debug=True, port=3000)
