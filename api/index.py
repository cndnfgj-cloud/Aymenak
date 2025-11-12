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

# ===== Send helpers =====
def fb_send(payload):
    if not PAGE_ACCESS_TOKEN:
        print("⚠️ PAGE_ACCESS_TOKEN is missing")
        return
    try:
        requests.post(
            GRAPH_URL,
            params={"access_token": PAGE_ACCESS_TOKEN},
            json=payload,
            timeout=25,
        )
    except Exception as e:
        print("❌ send error:", e)

def send_text(psid, text):
    fb_send({"recipient": {"id": psid}, "message": {"text": text}})

def send_quick(psid):
    """Quick replies: Developer + Share (تشتغل على Messenger وLite)."""
    payload = {
        "recipient": {"id": psid},
        "message": {
            "text": "اختر إجراء:",
            "quick_replies": [
                {"content_type": "text", "title": "👨‍💻 المطوّر", "payload": "DEV_INFO"},
                {"content_type": "text", "title": "📤 مشاركة", "payload": "SHARE_BOT"}
            ]
        }
    }
    fb_send(payload)

def send_share(psid):
    """Bubble مشاركة؛ في Lite يبقى زر الرابط يعمل كبديل."""
    payload = {
        "recipient": {"id": psid},
        "message": {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "generic",
                    "elements": [{
                        "title": "شارِك هذا البوت مع أصدقائك",
                        "subtitle": "ردود فورية — ساعدنا نكبر 🌟",
                        "buttons": [
                            {"type": "element_share"},
                            {"type": "web_url", "title": "👨‍💻 حساب المطوّر", "url": DEV_PROFILE_URL}
                        ]
                    }]
                }
            }
        }
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
    return "Verification failed", 403

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

            # Postbacks
            if "postback" in event:
                handle_postback(psid, (event["postback"] or {}).get("payload"))
                continue

            # Messages
            if "message" in event:
                msg = event["message"]
                # Quick reply payload
                qr = (msg.get("quick_reply") or {}).get("payload")
                if qr:
                    handle_postback(psid, qr)
                    continue

                if "text" in msg:
                    handle_message(psid, msg["text"])
                else:
                    send_text(psid, "أرسل رسالتك نصيًا فقط.")
                    send_quick(psid)

    return jsonify({"status": "ok"}), 200

# ===== Cleaning: remove time/date/dev/answer/TRX and quotes =====
CLEAN_PATTERNS = [
    r'(?i)t[\W_]*_?[\W_]*r[\W_]*_?[\W_]*x[\W_]*_?[\W_]*a[\W_]*i',  # T_R_X_AI variants
    r'(?i)\banswer\b',
    r'(?i)\bdate\b',
    r'(?i)\bdev\b',
    r'(?i)\btime\b',
    # ISO date 2025-11-12
    r'\b\d{4}-\d{2}-\d{2}\b',
    # common date 12/11/2025 or 12-11-25
    r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
    # time 14:05 or 2:05 PM
    r'\b\d{1,2}:\d{2}(:\d{2})?\s?(AM|PM|am|pm)?\b'
]

def clean_api_text(t: str) -> str:
    if not t:
        return ""
    # Remove labeled lines like "Answer: ..." / "Date: ..." / "Dev: ..." / "Time: ..."
    t = re.sub(r'(?im)^\s*(answer|date|dev|time)\s*:\s*.*$', '', t)
    # Remove target tokens/patterns wherever they appear
    for pat in CLEAN_PATTERNS:
        t = re.sub(pat, '', t)
    # Remove quotes/backticks
    t = t.replace('"', '').replace("'", '').replace("`", '')
    # Collapse extra whitespace and punctuation artifacts
    t = re.sub(r'\s+', ' ', t).strip()
    t = re.sub(r'^[\-\:\.\,;\/\s]+|[\-\:\.\,;\/\s]+$', '', t)
    return t

def short_brand_line():
    return "مساعد أيمن — رد فوري بإجابات مختصرة وقوية."

# ===== Logic =====
def handle_postback(psid, payload):
    p = (payload or "").upper()
    if p in ("GET_STARTED", "START"):
        send_text(psid, f"أهلًا 👋 {short_brand_line()}")
        send_quick(psid)
        return

    if p == "DEV_INFO":
        # المطلوب: يظهر رابط الحساب فقط
        send_text(psid, DEV_PROFILE_URL)
        return

    if p == "SHARE_BOT":
        send_share(psid)
        return

    send_text(psid, "جاهز لخدمتك.")
    send_quick(psid)

def handle_message(psid, text):
    msg = (text or "").strip().lower()

    # تحية مختصرة جدًا كما طلبت
    if "السلام عليكم" in msg or msg.startswith("سلام") or msg == "كيف حالك":
        send_text(psid, "مرحبا")
        send_quick(psid)
        return

    # هوية المطوّر
    if any(kw in msg for kw in ["مطورك", "من مطورك", "من صنعك", "من أنشأك", "من انشأك"]):
        send_text(psid, "aymen bourai هو مطوري وأنا مطيع له وأبقى مساعدًا له.")
        send_text(psid, DEV_PROFILE_URL)
        return

    # ذكر اسم المطوّر
    if "aymen bourai" in msg or ("aymen" in msg and "bourai" in msg):
        send_text(psid, "نعم، aymen bourai هو مطوري، عمره 18 سنة من مواليد 2007، شاب مبرمج لتطبيقات ومواقع يحب البرمجة وأتمنى له مستقبل باهر. من ناحية الدراسة لا أعلم، وهو شخص انطوائي يحب العزلة.")
        return

    # الرد العام عبر API + التنظيف القوي
    try:
        r = requests.get(GPT_API, params={"text": text}, timeout=25)
        raw = r.text or ""
        cleaned = clean_api_text(raw)
        if not cleaned:
            cleaned = "حاضر."
    except Exception as e:
        cleaned = f"حدث خطأ أثناء الاتصال بالخدمة: {e}"

    send_text(psid, cleaned)
    send_quick(psid)

@app.route("/api/healthz")
def healthz():
    return jsonify({"ok": True})
