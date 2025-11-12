import os
import re
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ===== الإعداد =====
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "boykta 2023")
GPT_API = "https://app.claila.com/api/v2/unichat2"
DEV_PROFILE_URL = os.getenv("DEV_PROFILE_URL", "https://www.facebook.com/aymen.bourai.2025")

GRAPH_URL = "https://graph.facebook.com/v17.0/me/messages"

# ===== إرسال عبر Facebook API =====
def fb_send(payload):
    try:
        requests.post(
            GRAPH_URL,
            params={"access_token": PAGE_ACCESS_TOKEN},
            json=payload,
            timeout=25,
        )
    except Exception as e:
        print("❌ إرسال فشل:", e)

def send_text(psid, text):
    fb_send({"recipient": {"id": psid}, "message": {"text": text}})

def send_quick(psid):
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
    payload = {
        "recipient": {"id": psid},
        "message": {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "generic",
                    "elements": [{
                        "title": "شارك هذا البوت مع أصدقائك 🚀",
                        "subtitle": "ذكاء فوري من تطوير aymen bourai",
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

# ===== التحقق من Webhook =====
@app.route("/api/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "فشل التحقق", 403

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

            # الرد على الأزرار أو الرسائل
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
                    send_text(psid, "أرسل لي نص فقط 💬")
                    send_quick(psid)
    return jsonify({"status": "ok"}), 200

# ===== تنظيف النص القادم من API =====
def clean_api_text(raw):
    if not raw:
        return ""
    try:
        data = requests.utils.json.loads(raw)
        vals = list(data.values())
        # خذ أول نص عربي واضح
        arabic = [v for v in vals if any("\u0600" <= ch <= "\u06FF" for ch in v)]
        txt = arabic[0] if arabic else vals[0] if vals else ""
    except Exception:
        txt = raw

    # إزالة الوقت والتاريخ والكلمات الزائدة
    txt = re.sub(r'(?i)(answer|date|dev|time)\s*[:：]\s*.*', '', txt)
    txt = re.sub(r'\d{4}-\d{2}-\d{2}.*', '', txt)
    txt = re.sub(r'\b\d{1,2}:\d{2}(:\d{2})?\b', '', txt)
    txt = re.sub(r'http\S+|www\S+|@\S+', '', txt)
    txt = txt.replace('"', '').replace("'", '').replace("`", '')
    txt = re.sub(r'\s+', ' ', txt).strip()
    return txt or "جاهز."

# ===== الردود =====
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

    # تحية
    if "السلام عليكم" in msg or msg.startswith("سلام") or msg == "كيف حالك":
        send_text(psid, "مرحبا")
        send_quick(psid)
        return

    # مطورك
    if any(kw in msg for kw in ["مطورك", "من مطورك", "من صنعك", "من أنشأك"]):
        send_text(psid, "aymen bourai هو مطوري وأنا مطيع له وأبقى مساعدًا له.")
        send_text(psid, DEV_PROFILE_URL)
        return

    # اسم المطور
    if "aymen bourai" in msg:
        send_text(psid, "نعم، aymen bourai هو مطوري، عمره 18 سنة من مواليد 2007، شاب مبرمج لتطبيقات ومواقع يحب البرمجة وأتمنى له مستقبل باهر. من ناحية الدراسة لا أعلم، وهو شخص انطوائي يحب العزلة.")
        return

    # طلب عادي من المستخدم
    try:
        r = requests.get(GPT_API, params={"text": text}, timeout=20)
        reply = clean_api_text(r.text)
    except Exception as e:
        reply = f"حدث خطأ أثناء الاتصال بالخدمة: {e}"

    send_text(psid, reply)
    send_quick(psid)

@app.route("/api/healthz")
def healthz():
    return jsonify({"ok": True})
