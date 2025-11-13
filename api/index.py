import os
import re
import json
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ===== Settings =====
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "boykta 2023")
GPT_API = "https://vetrex.x10.mx/api/gpt4.php"
DEV_PROFILE_URL = os.getenv("DEV_PROFILE_URL", "https://www.facebook.com/aymen.bourai.2025")
GRAPH_URL = "https://graph.facebook.com/v17.0/me/messages"

FALLBACK_MSG = "أنا هنا لمساعدتك — اسألني أي شيء 👌"

# ===== FB send helpers =====
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
        print("⚠️ send error:", e)


def send_text(psid, text):
    fb_send({"recipient": {"id": psid}, "message": {"text": text}})


# ===== Verify =====
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

            # Postbacks
            if "postback" in event:
                handle_postback(psid, event["postback"].get("payload", ""))
                continue

            # Messages
            if "message" in event:
                msg = event["message"]
                if "text" in msg:
                    handle_message(psid, msg["text"])
                else:
                    send_text(psid, "أرسل نصًا فقط 💬")

    return jsonify({"status": "ok"}), 200


# ===== Cleaning helpers =====
DISALLOWED_RE = re.compile(
    r'(?i)('
    r'\bdate\b|'
    r'\banswer\b|'
    r'\bdev\b|'
    r't[_\W-]*r[_\W-]*x[_\W-]*a[_\W-]*i|'  # T_R_X_AI بأشكاله
    r'dont\s*forget\s*to\s*support\s*the\s*channel'
    r')'
)
LINK_OR_AT_RE = re.compile(r'http\S+|www\.\S+|@\S+')
TIME_RE = re.compile(r'\b\d{1,2}:\d{2}(:\d{2})?\s*(AM|PM|am|pm)?\b')
ISO_DATE_RE = re.compile(r'\d{4}-\d{2}-\d{2}')
PUNCT_RE = re.compile(r'["\'`{}]+')
WS_RE = re.compile(r'\s+')


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


def clean_api_reply(raw_text: str) -> str:
    """
    يرجع جواب طويل ونظيف:
    - يحذف date / answer / dev / T_R_X_AI / Don't forget...
      والروابط / الأوقات / التواريخ / الأقواس
    - يحافظ على أكثر من جملة (مش قصير)
    """
    if not raw_text:
        return ""

    text = raw_text

    # لو الرد JSON → نجمع القيم في نص واحد
    try:
        parsed = json.loads(raw_text)
        vals = _flatten_json_values(parsed)
        if vals:
            text = "\n".join(vals)
    except Exception:
        pass

    # ننظف سطر بسطر، ونحتفظ بكل السطور المفيدة
    lines = (text or "").replace("\r", "").split("\n")
    cleaned_lines = []

    for line in lines:
        s = (line or "").strip()
        if not s:
            continue

        # تنظيف على مستوى السطر
        s = LINK_OR_AT_RE.sub("", s)   # روابط و @
        s = TIME_RE.sub("", s)         # أوقات
        s = ISO_DATE_RE.sub("", s)     # تواريخ ISO
        s = PUNCT_RE.sub("", s)        # أقواس واقتباسات
        s = DISALLOWED_RE.sub("", s)   # date/answer/dev/T_R_X_AI/Don't forget...
        s = s.replace(":", " ")
        s = WS_RE.sub(" ", s).strip()

        if len(s) < 3:
            continue

        cleaned_lines.append(s)

    if not cleaned_lines:
        # fallback: نظف النص الخام وخذ جزء طويل معقول
        fallback = PUNCT_RE.sub("", raw_text)
        fallback = WS_RE.sub(" ", fallback).strip()
        return fallback[:900]

    # نجمع السطور في فقرة طويلة
    result = "\n\n".join(cleaned_lines)

    # حد أقصى للطول حتى لا يختنق المسنجر (حوالي 900 حرف)
    if len(result) > 900:
        result = result[:900].rstrip()

    return result


# ===== Logic =====
def handle_postback(psid, payload):
    p = (payload or "").upper()
    if p in ("GET_STARTED", "START"):
        # ترحيب بدون أزرار
        send_text(
            psid,
            "👋 مرحبًا! أنا مساعد أيمن — ذكاء فوري بإجابات قوية وطويلة تشرح لك كل شيء ببساطة."
        )
        return

    # باقي الـ payloads (لو حصلت) → رد عام
    send_text(psid, FALLBACK_MSG)


def handle_message(psid, text):
    msg = text.strip().lower()
    msg_norm = msg.replace("؟", "").strip()

    # تحيات
    if "السلام عليكم" in msg or msg.startswith("سلام") or msg == "كيف حالك":
        send_text(psid, "مرحبا")
        return

    # من أنت؟
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
            "أنا مساعد ذكاء اصطناعي أردّ مباشرة على أسئلتك بإجابات مفصّلة وواضحة. "
            "مطوري هو aymen bourai وأنا مطيع له وأبقى مساعدًا له."
        )
        return

    # مطورك؟
    if any(kw in msg for kw in ["مطورك", "من مطورك", "من صنعك", "من أنشأك"]):
        send_text(psid, "aymen bourai هو مطوري وأنا مطيع له وأبقى مساعدًا له.")
        send_text(psid, DEV_PROFILE_URL)
        return

    # ذكر اسم المطوّر
    if "aymen bourai" in msg:
        send_text(
            psid,
            "نعم، aymen bourai هو مطوري، عمره 18 سنة من مواليد 2007، شاب مبرمج لتطبيقات ومواقع يحب البرمجة "
            "وأتمنى له مستقبل باهر. من ناحية الدراسة لا أعلم، وهو شخص انطوائي يحب العزلة."
        )
        return

    # الافتراضي: API + تنظيف + بديل ذكي
    try:
        r = requests.get(GPT_API, params={"text": text}, timeout=20)
        reply = clean_api_reply(r.text or "")
    except Exception as e:
        reply = f"حدث خطأ أثناء الاتصال بالخدمة: {e}"

    if not reply:
        reply = FALLBACK_MSG

    send_text(psid, reply)


# Health
@app.route("/api/healthz")
def healthz():
    return jsonify({"ok": True})
