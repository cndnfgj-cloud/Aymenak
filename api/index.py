import os
import re
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ===== الإعدادات =====
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "boykta 2023")
GPT_API = "https://vetrex.x10.mx/api/gpt4.php"
DEV_PROFILE_URL = os.getenv("DEV_PROFILE_URL", "https://www.facebook.com/aymen.bourai.2025")
GRAPH_URL = "https://graph.facebook.com/v17.0/me/messages"


# ===== إرسال عبر فيسبوك =====
def fb_send(payload):
    try:
        requests.post(
            GRAPH_URL,
            params={"access_token": PAGE_ACCESS_TOKEN},
            json=payload,
            timeout=20,
        )
    except Exception as e:
        print("⚠️ فشل الإرسال:", e)


def send_text(psid, text):
    fb_send({"recipient": {"id": psid}, "message": {"text": text}})


def send_quick(psid):
    payload = {
        "recipient": {"id": psid},
        "message": {
            "text": "اختر إجراء:",
            "quick_replies": [
                {"content_type": "text", "title": "👨‍💻 المطوّر", "payload": "DEV_INFO"},
                {"content_type": "text", "title": "📤 مشاركة", "payload": "SHARE_BOT"},
            ],
        },
    }
    fb_send(payload)


def send_share(psid):
    payload = {
        "recipient": {"id": psid},
        "message": {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "generic",
                    "elements": [
                        {
                            "title": "شارك هذا البوت مع أصدقائك 🚀",
                            "subtitle": "ذكاء فوري من تطوير aymen bourai",
                            "buttons": [
                                {"type": "element_share"},
                                {"type": "web_url", "title": "👨‍💻 حساب المطوّر", "url": DEV_PROFILE_URL},
                            ],
                        }
                    ],
                },
            }
        },
    }
    fb_send(payload)


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
            psid = event.get("sender", {}).get("id")
            if not psid:
                continue

            if "postback" in event:
                handle_postback(psid, event["postback"].get("payload", ""))
                continue

            if "message" in event:
                msg = event["message"]
                qr = (msg.get("quick_reply") or {}).get("payload")
                if qr:
                    handle_postback(psid, qr)
                    continue
                if "text" in msg:
                    handle_message(psid, msg["text"])
                else:
                    send_text(psid, "أرسل نصًا فقط 💬")
                    send_quick(psid)

    return jsonify({"status": "ok"}), 200


# ===== تنظيف الرد =====
def clean_api_reply(raw_text: str) -> str:
    """ينظف النص من الوقت، التاريخ، dev، answer، الرموز، ويحتفظ فقط بجملة مفيدة."""
    if not raw_text:
        return ""

    # حاول استخراج من JSON
    try:
        data = requests.utils.json.loads(raw_text)
        values = list(data.values())
        # خذ أول نص عربي واضح
        arabic = [v for v in values if any("\u0600" <= ch <= "\u06FF" for ch in v)]
        text = arabic[0] if arabic else values[0] if values else raw_text
    except Exception:
        text = raw_text

    # فلترة قوية
    text = re.sub(r'(?i)(answer|date|dev|time|t[_\-]?r[_\-]?x[_\-]?a[_\-]?i)', '', text)
    text = re.sub(r'\d{4}-\d{2}-\d{2}.*', '', text)
    text = re.sub(r'\b\d{1,2}:\d{2}(:\d{2})?\b', '', text)
    text = re.sub(r'http\S+|www\S+|@\S+', '', text)
    text = text.replace('"', '').replace("'", '').replace("`", '')
    text = re.sub(r'\s+', ' ', text).strip()

    # فقط الجملة العربية المفيدة
    lines = text.splitlines()
    for line in lines:
        if any("\u0600" <= ch <= "\u06FF" for ch in line) and len(line) > 5:
            return line.strip()

    return text or "جاهز."


# ===== منطق الردود =====
def handle_postback(psid, payload):
    p = (payload or "").upper()
    if p in ("GET_STARTED", "START"):
        send_text(psid, "👋 مرحبًا! أنا مساعد أيمن — ذكاء فوري بإجابات مختصرة وقوية.")
        send_quick(psid)
        return
    if p == "DEV_INFO":
        send_text(psid, DEV_PROFILE_URL)
        return
    if p == "SHARE_BOT":
        send_share(psid)
        return
    send_text(psid, "جاهز.")
    send_quick(psid)


def handle_message(psid, text):
    msg = text.strip().lower()

    # تحية بسيطة
    if "السلام عليكم" in msg or msg.startswith("سلام") or msg == "كيف حالك":
        send_text(psid, "مرحبا")
        send_quick(psid)
        return

    # معلومات المطوّر
    if any(kw in msg for kw in ["مطورك", "من مطورك", "من صنعك", "من أنشأك"]):
        send_text(psid, "aymen bourai هو مطوري وأنا مطيع له وأبقى مساعدًا له.")
        send_text(psid, DEV_PROFILE_URL)
        return

    if "aymen bourai" in msg:
        send_text(psid, "نعم، aymen bourai هو مطوري، عمره 18 سنة من مواليد 2007، شاب مبرمج لتطبيقات ومواقع يحب البرمجة وأتمنى له مستقبل باهر. من ناحية الدراسة لا أعلم، وهو شخص انطوائي يحب العزلة.")
        return

    # الرد من API
    try:
        r = requests.get(GPT_API, params={"text": text}, timeout=20)
        reply = clean_api_reply(r.text)
    except Exception as e:
        reply = f"حدث خطأ أثناء الاتصال بالخدمة: {e}"

    send_text(psid, reply)
    send_quick(psid)


@app.route("/api/healthz")
def healthz():
    return jsonify({"ok": True})
