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

def send_quick_menu(psid):
    """Quick replies under the message (works on Messenger & Lite)."""
    payload = {
        "recipient": {"id": psid},
        "message": {
            "text": "اختر إجراء سريع:",
            "quick_replies": [
                {"content_type": "text", "title": "🤖 معلومات الذكاء", "payload": "AI_INFO"},
                {"content_type": "text", "title": "👨‍💻 المطوّر", "payload": "DEV_INFO"},
                {"content_type": "text", "title": "📤 مشاركة", "payload": "SHARE_BOT"},
                {"content_type": "text", "title": "🧭 قائمة", "payload": "SHOW_MENU"}
            ]
        }
    }
    fb_send(payload)

def send_generic_menu(psid):
    """Generic template with element_share (for Messenger; Lite shows at least URL buttons)."""
    payload = {
        "recipient": {"id": psid},
        "message": {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "generic",
                    "elements": [{
                        "title": "مساعد Aymen — بوت الذكاء الاصطناعي",
                        "subtitle": "اسألني أي شيء. استخدم الأزرار بالأسفل.",
                        "default_action": {
                            "type": "web_url",
                            "url": DEV_PROFILE_URL,
                            "webview_height_ratio": "tall"
                        },
                        "buttons": [
                            {"type": "postback", "title": "🤖 معلومات الذكاء", "payload": "AI_INFO"},
                            {"type": "web_url", "title": "👨‍💻 حساب المطوّر", "url": DEV_PROFILE_URL},
                            {"type": "postback", "title": "🧭 قائمة", "payload": "SHOW_MENU"}
                        ]
                    }]
                }
            }
        }
    }
    fb_send(payload)

def send_share_bubble(psid):
    """Send a share button bubble; on Lite the URL button remains usable."""
    payload = {
        "recipient": {"id": psid},
        "message": {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "generic",
                    "elements": [{
                        "title": "شارِك هذا البوت مع أصدقائك",
                        "subtitle": "ساعدنا نكبر 🌟",
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

# ===== Incoming Events =====
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
                handle_postback(psid, (event["postback"] or {}).get("payload"))
                continue

            if "message" in event:
                msg = event["message"]
                # quick replies come as normal message with payload
                qr_payload = (msg.get("quick_reply") or {}).get("payload")
                if qr_payload:
                    handle_postback(psid, qr_payload)
                    continue

                if "text" in msg:
                    handle_message(psid, msg["text"])
                else:
                    send_text(psid, "أرسل رسالتك نصيًا فقط.")
                    send_quick_menu(psid)
                    send_generic_menu(psid)

    return jsonify({"status": "ok"}), 200

def handle_postback(psid, payload):
    p = (payload or "").upper()
    if p in ("GET_STARTED", "START", "SHOW_MENU"):
        send_text(psid, "مرحبًا 👋 أنا بوت ذكاء اصطناعي. اكتب أي سؤال أو استخدم الخيارات.")
        send_quick_menu(psid)
        send_generic_menu(psid)
        return

    if p == "AI_INFO":
        send_text(psid, "أنا ذكاء اصطناعي — أجيب عن أسئلتك وأساعدك بالمعلومات.")
        return

    if p == "DEV_INFO":
        send_text(psid, "aymen bourai هو مطوري وأنا مطيع له وأبقى مساعدًا له.")
        send_text(psid, f"زور حسابه: {DEV_PROFILE_URL}")
        return

    if p == "SHARE_BOT":
        send_share_bubble(psid)
        return

    send_text(psid, "لم أفهم الاختيار. هذه القائمة:")
    send_quick_menu(psid)
    send_generic_menu(psid)

def clean_api_text(t: str) -> str:
    if not t:
        return ""
    # remove T_R_X_AI with flexible separators/case
    t = re.sub(r'(?i)t[\W_]*_?[\W_]*r[\W_]*_?[\W_]*x[\W_]*_?[\W_]*a[\W_]*i', '', t)
    return t.strip()

def handle_message(psid, text):
    msg = (text or "").strip().lower()

    # Custom greetings
    if "السلام عليكم" in msg or msg.startswith("سلام"):
        send_text(psid, "وعليكم السلام ورحمة الله وبركاته")
        send_text(psid, "أنا ذكاء اصطناعي 🤖")
        send_quick_menu(psid)
        return

    # Developer identity questions
    if any(kw in msg for kw in ["مطورك", "من مطورك", "من صنعك", "من أنشأك", "من انشأك"]):
        send_text(psid, "aymen bourai هو مطوري وأنا مطيع له وأبقى مساعدًا له.")
        send_text(psid, f"تعرف عليه أكثر: {DEV_PROFILE_URL}")
        return

    # When user mentions aymen bourai
    if "aymen bourai" in msg or ("aymen" in msg and "bourai" in msg):
        send_text(psid, "نعم، aymen bourai هو مطوري، عمره 18 سنة من مواليد 2007، شاب يبرمج تطبيقات ومواقع ويحب البرمجة، وأتمنى له مستقبل باهر. من ناحية الدراسة لا أعلم، وهو شخص انطوائي يحب العزلة.")
        return

    # General answer via external API
    try:
        r = requests.get(GPT_API, params={"text": text}, timeout=25)
        raw = r.text or ""
        cleaned = clean_api_text(raw)
        if not cleaned:
            cleaned = "لم أفهم سؤالك، حاول صياغته بشكل أوضح 😊"
    except Exception as e:
        cleaned = f"حدث خطأ أثناء الاتصال بالخدمة: {e}"

    send_text(psid, cleaned)
    # Encourage more interactions
    send_quick_menu(psid)

@app.route("/api/healthz")
def healthz():
    return jsonify({"ok": True})
