import os
import re
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ===== Settings =====
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "boykta 2023")
GPT_API = "https://vetrex.x10.mx/api/gpt4.php"
DEV_PROFILE_URL = os.getenv("DEV_PROFILE_URL", "https://www.facebook.com/aymen.bourai.2025")
GRAPH_URL = "https://graph.facebook.com/v17.0/me/messages"

# ===== Facebook send helpers =====
def fb_send(payload):
    try:
        requests.post(
            GRAPH_URL,
            params={"access_token": PAGE_ACCESS_TOKEN},
            json=payload,
            timeout=20,
        )
    except Exception as e:
        print("⚠️ send error:", e)

def send_text(psid, text):
    fb_send({"recipient": {"id": psid}, "message": {"text": text}})

def send_quick(psid):
    # Minimal, works on Messenger & Lite
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

# ===== Incoming =====
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

# ===== Cleaning & extraction =====
BLOCK_PATTERNS = [
    r'(?i)(answer|date|dev|time)\s*[:：]\s*.*',  # labeled lines
    r'(?i)t[_\W-]*r[_\W-]*x[_\W-]*a[_\W-]*i', # T_R_X_AI variants
    r'(?i)dont\s*forget.*',                     # "Don't forget to support the channel"
]

REMOVE_INLINE = [
    (r'\d{4}-\d{2}-\d{2}.*', ''),              # ISO date + trailing
    (r'\b\d{1,2}:\d{2}(:\d{2})?\s*(AM|PM|am|pm)?\b', ''),  # times
    (r'http\S+|www\S+|@\S+', ''),             # links and @handles
    (r'["\' + "`" + r']', ''),                   # quotes/backticks
    (r'[:{}]', ''),                               # colons/braces
]

def extract_arabic_sentence(text: str) -> str:
    # Keep the first meaningful Arabic sentence
    for part in re.split(r'[\n\r]+', text):
        part = part.strip()
        if any('\u0600' <= ch <= '\u06FF' for ch in part) and len(part) > 4:
            return part
    return ""

def clean_api_reply(raw_text: str) -> str:
    if not raw_text:
        return ""

    # Try JSON -> take first Arabic-looking value
    text = raw_text
    try:
        data = requests.utils.json.loads(raw_text)
        vals = list(data.values())
        arabic_vals = [v for v in vals if isinstance(v, str) and any('\u0600' <= ch <= '\u06FF' for ch in v)]
        text = (arabic_vals[0] if arabic_vals else (vals[0] if vals else raw_text))
        if not isinstance(text, str):
            text = str(text)
    except Exception:
        pass

    # Remove whole lines that match block patterns
    for pat in BLOCK_PATTERNS:
        text = re.sub(pat, '', text, flags=re.MULTILINE)

    # Inline removals
    for pat, repl in REMOVE_INLINE:
        text = re.sub(pat, repl, text)

    # Collapse spaces
    text = re.sub(r'\s+', ' ', text).strip()

    # Extract the first meaningful Arabic sentence only
    only = extract_arabic_sentence(text)
    if only:
        return only

    # Fallback: if nothing Arabic, just return cleaned text (or default)
    return text or "جاهز."

# ===== Logic =====
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

    # Greetings
    if "السلام عليكم" in msg or msg.startswith("سلام") or msg == "كيف حالك":
        send_text(psid, "مرحبا")
        send_quick(psid)
        return

    # Developer identity
    if any(kw in msg for kw in ["مطورك", "من مطورك", "من صنعك", "من أنشأك"]):
        send_text(psid, "aymen bourai هو مطوري وأنا مطيع له وأبقى مساعدًا له.")
        send_text(psid, DEV_PROFILE_URL)
        return

    if "aymen bourai" in msg:
        send_text(psid, "نعم، aymen bourai هو مطوري، عمره 18 سنة من مواليد 2007، شاب مبرمج لتطبيقات ومواقع يحب البرمجة وأتمنى له مستقبل باهر. من ناحية الدراسة لا أعلم، وهو شخص انطوائي يحب العزلة.")
        return

    # Default: call API and clean
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
