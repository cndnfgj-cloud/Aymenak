import os
import re
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "boykta 2023")
GPT_API = "https://vetrex.x10.mx/api/gpt4.php"
DEV_PROFILE_URL = os.getenv("DEV_PROFILE_URL", "https://www.facebook.com/aymen.bourai.2025")
GRAPH_URL = "https://graph.facebook.com/v17.0/me/messages"


def fb_send(payload):
    try:
        requests.post(GRAPH_URL, params={"access_token": PAGE_ACCESS_TOKEN}, json=payload, timeout=20)
    except Exception as e:
        print("⚠️ send error:", e)


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


@app.route("/api/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "خطأ في التحقق", 403


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


DISALLOWED_RE = re.compile(r'(?i)(\bdate\b|\banswer\b|\bdev\b|dont\s*forget\s*to\s*support\s*the\s*channel)')
LINK_OR_AT_RE = re.compile(r'http\S+|www\.\S+|@\S+')
TIME_RE = re.compile(r'\b\d{1,2}:\d{2}(:\d{2})?\s*(AM|PM|am|pm)?\b')
ISO_DATE_RE = re.compile(r'\d{4}-\d{2}-\d{2}')
ARABIC_CHAR_RE = re.compile(r'[\u0600-\u06FF]')


def clean_api_reply(raw_text: str) -> str:
    if not raw_text:
        return "جاهز."

    text = raw_text
    try:
        parsed = requests.utils.json.loads(raw_text)
        if isinstance(parsed, dict):
            vals = [str(v) for v in parsed.values()]
            text = "\n".join(vals)
        elif isinstance(parsed, list):
            vals = [str(v) for v in parsed]
            text = "\n".join(vals)
        else:
            text = str(parsed)
    except Exception:
        pass

    text = text.replace("{", " ").replace("}", " ").replace("[", " ").replace("]", " ")
    text = text.replace('"', " ").replace("'", " ").replace("`", " ")

    candidates = []
    for part in re.split(r'[\n\r]+|,|؛|\|', text):
        s = part.strip()
        if not s:
            continue
        s = LINK_OR_AT_RE.sub("", s)
        s = TIME_RE.sub("", s)
        s = ISO_DATE_RE.sub("", s)
        if DISALLOWED_RE.search(s):
            continue
        s = s.replace(":", " ")
        s = re.sub(r'\s+', ' ', s).strip()
        if len(s) < 3:
            continue
        candidates.append(s)

    for s in candidates:
        if ARABIC_CHAR_RE.search(s) and len(s) > 4:
            return s

    if candidates:
        return candidates[0]
    return "جاهز."


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
    if "السلام عليكم" in msg or msg.startswith("سلام") or msg == "كيف حالك":
        send_text(psid, "مرحبا")
        send_quick(psid)
        return
    if any(kw in msg for kw in ["مطورك", "من مطورك", "من صنعك", "من أنشأك"]):
        send_text(psid, "aymen bourai هو مطوري وأنا مطيع له وأبقى مساعدًا له.")
        send_text(psid, DEV_PROFILE_URL)
        return
    if "aymen bourai" in msg:
        send_text(psid, "نعم، aymen bourai هو مطوري، عمره 18 سنة من مواليد 2007، شاب مبرمج لتطبيقات ومواقع يحب البرمجة وأتمنى له مستقبل باهر. من ناحية الدراسة لا أعلم، وهو شخص انطوائي يحب العزلة.")
        return
    try:
        r = requests.get(GPT_API, params={"text": text}, timeout=20)
        reply = clean_api_reply(r.text or "")
    except Exception as e:
        reply = f"حدث خطأ أثناء الاتصال بالخدمة: {e}"
    send_text(psid, reply)
    send_quick(psid)


@app.route("/api/healthz")
def healthz():
    return jsonify({"ok": True})
