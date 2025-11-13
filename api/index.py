import os
import re
import random
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ===== إعدادات أساسية =====
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "boykta 2023")
DEV_PROFILE_URL = os.getenv("DEV_PROFILE_URL", "https://www.facebook.com/aymen.bourai.2025")
GRAPH_URL = "https://graph.facebook.com/v17.0/me/messages"

CLAILA_URL = "https://app.claila.com/api/v2/unichat2"
FALLBACK_MSG = "أنا هنا لمساعدتك — اسألني أي شيء 👌"

# ===== إرسال إلى فيسبوك =====
def fb_send(payload):
    try:
        r = requests.post(
            GRAPH_URL,
            params={"access_token": PAGE_ACCESS_TOKEN},
            json=payload,
            timeout=20,
        )
        print("FB send:", r.status_code, r.text[:200])
    except Exception as e:
        print("⚠️ FB send error:", e)

def send_text(psid, text):
    fb_send({"recipient": {"id": psid}, "message": {"text": text}})

def send_quick(psid):
    # زر واحد فقط: المطوّر
    payload = {
        "recipient": {"id": psid},
        "message": {
            "text": "اختر إجراء:",
            "quick_replies": [
                {"content_type": "text", "title": "👨‍💻 المطوّر", "payload": "DEV_INFO"},
            ],
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

# ===== استقبال الرسائل من فيسبوك =====
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

            # postback (GET_STARTED أو غيره)
            if "postback" in event:
                handle_postback(psid, event["postback"].get("payload", ""))
                continue

            # رسالة عادية
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

# ===== تنظيف رد الـ API =====

# الكلمات/الجمل الممنوعة
DISALLOWED_RE = re.compile(
    r'(?i)('
    r'\bdate\b|'
    r'\banswer\b|'
    r'\bdev\b|'
    r't[_\W-]*r[_\W-]*x[_\W-]*a[_\W-]*i|'  # T_R_X_AI بأشكالها
    r'dont\s*forget\s*to\s*support\s*the\s*channel'
    r')'
)

LINK_OR_AT_RE = re.compile(r'http\S+|www\.\S+|@\S+')
TIME_RE       = re.compile(r'\b\d{1,2}:\d{2}(:\d{2})?\s*(AM|PM|am|pm)?\b')
ISO_DATE_RE   = re.compile(r'\d{4}-\d{2}-\d{2}')
PUNCT_RE      = re.compile(r'["\'`{}]+')
WS_RE         = re.compile(r'\s+')

def _flatten_json_values(obj):
    out = []
    if isinstance(obj, dict):
        for v in obj.values():
            out.extend(_flatten_json_values(v))
    elif isinstance(obj, list):
        for v in obj:
            out.extend(_flatten_json_values(v))
    elif isinstance(obj, (str, int, float, bool)):
        out.append(str(obj))
    return out

def pick_sentence(text: str) -> str:
    """اختر أول جملة مفيدة، نفضّل العربية لكن نقبل أي جملة نظيفة."""
    parts = re.split(r'[\n\r]+|[;|،,]', text)
    arabic = None
    first  = None

    for part in parts:
        s = (part or "").strip()
        if not s:
            continue

        # تنظيف خفيف للسطر
        s = LINK_OR_AT_RE.sub("", s)        # remove links/@
        s = TIME_RE.sub("", s)              # remove times
        s = ISO_DATE_RE.sub("", s)          # remove ISO dates
        s = PUNCT_RE.sub("", s)             # remove quotes/braces
        s = DISALLOWED_RE.sub("", s)        # remove forbidden words (answer/date/dev/T_R_X_AI/Don't forget..)
        s = s.replace(":", " ")
        s = WS_RE.sub(" ", s).strip()

        if len(s) < 3:
            continue

        if first is None:
            first = s

        if any('\u0600' <= ch <= '\u06FF' for ch in s):
            arabic = s
            break

    return arabic or first or ""

def clean_api_reply(raw_text: str) -> str:
    """ترجع جملة مفيدة فقط بدون date/answer/dev/T_R_X_AI ولا Don't forget ولا أقواس وروابط."""
    if not raw_text:
        return ""

    text = raw_text

    # لو الرد JSON نجمع القيم فقط
    try:
        parsed = requests.utils.json.loads(raw_text)
        vals = _flatten_json_values(parsed)
        if vals:
            text = "\n".join(vals)
    except Exception:
        pass

    s = pick_sentence(text)
    if s:
        return s

    # fallback: نظّف الخام وخذ أول 120 حرف
    fallback = PUNCT_RE.sub("", raw_text)
    fallback = WS_RE.sub(" ", fallback).strip()
    return fallback[:120]

# ===== استدعاء Claila API =====
def call_claila(prompt: str) -> str:
    session_id = "".join(random.choice("0123456789") for _ in range(10))

    payload = {
        "model": "gpt-4.1-mini",
        "calltype": "completion",
        "message": prompt,
        "sessionId": session_id,
        "chat_mode": "chat",
        "websearch": "false",
    }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 10; Mobile) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/141.0.0.0 Mobile Safari/537.36"
        ),
        "sec-ch-ua-platform": "\"Android\"",
        "sec-ch-ua": "\"Google Chrome\";v=\"141\", \"Not?A_Brand\";v=\"8\", \"Chromium\";v=\"141\"",
        "sec-ch-ua-mobile": "?1",
        "x-requested-with": "XMLHttpRequest",
        "origin": "https://app.claila.com",
        "sec-fetch-site": "same-origin",
        "sec-fetch-mode": "cors",
        "sec-fetch-dest": "empty",
        "referer": "https://app.claila.com/chat?uid=3887ac09&lang=ar",
        "accept-language": "ar-IQ,ar;q=0.9",
        "priority": "u=1, i",
    }

    try:
        r = requests.post(CLAILA_URL, data=payload, headers=headers, timeout=30)
        print("Claila:", r.status_code, r.text[:200])
        cleaned = clean_api_reply(r.text or "")
        return cleaned or ""
    except Exception as e:
        print("⚠️ Claila error:", e)
        return ""

# ===== منطق الردود =====
def handle_postback(psid, payload):
    p = (payload or "").upper()

    if p in ("GET_STARTED", "START"):
        # ترحيب احترافي قصير يجذب هيبة
        send_text(psid, "👋 أهلاً بك، أنا مساعد أيمن الذكي — أجاوبك فوراً وبأسلوب مختصر وقوي.")
        send_quick(psid)
        return

    if p == "DEV_INFO":
        # زر المطوّر → يرسل رابط حسابك فقط
        send_text(psid, DEV_PROFILE_URL)
        return

    # أي شيء آخر
    send_text(psid, FALLBACK_MSG)
    send_quick(psid)

def handle_message(psid, text):
    msg = text.strip().lower()
    msg_norm = msg.replace("؟", "").strip()

    # تحيات أساسية
    if "السلام عليكم" in msg or msg.startswith("سلام") or msg == "كيف حالك":
        send_text(psid, "مرحبا")
        send_quick(psid)
        return

    # من انت؟
    if any(
        kw in msg_norm
        for kw in [
            "من انت",
            "مين انت",
            "من تكون",
            "who are you",
            "what are you",
            "شكون انت",
            "شكون نت",
        ]
    ):
        send_text(
            psid,
            "أنا مساعد ذكاء اصطناعي أردّ مباشرة على أسئلتك. مطوري هو aymen bourai وأنا مطيع له وأبقى مساعدًا له.",
        )
        send_quick(psid)
        return

    # مطورك / من صنعك / من أنشأك
    if any(kw in msg for kw in ["مطورك", "من مطورك", "من صنعك", "من أنشأك"]):
        send_text(psid, "aymen bourai هو مطوري وأنا مطيع له وأبقى مساعدًا له.")
        send_text(psid, DEV_PROFILE_URL)
        send_quick(psid)
        return

    # لو كتبوا اسمك
    if "aymen bourai" in msg:
        send_text(
            psid,
            "نعم، aymen bourai هو مطوري، عمره 18 سنة من مواليد 2007، شاب مبرمج لتطبيقات ومواقع يحب البرمجة وأتمنى له مستقبل باهر. من ناحية الدراسة لا أعلم، وهو شخص انطوائي يحب العزلة.",
        )
        send_quick(psid)
        return

    # الافتراضي: استدعاء Claila وتنظيف الرد إلى جملة مفيدة فقط
    reply = call_claila(text)

    if not reply:
        reply = FALLBACK_MSG

    send_text(psid, reply)
    send_quick(psid)

# ===== Health Check =====
@app.route("/api/healthz")
def healthz():
    return jsonify({"ok": True})
