import os
import json
import random
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ===== إعدادات أساسية =====
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "boykta 2023")
GRAPH_URL = "https://graph.facebook.com/v17.0/me/messages"

CLAILA_URL = "https://app.claila.com/api/v2/unichat2"

# ===== إرسال لواجهة فيسبوك =====
def fb_send(payload):
    try:
        r = requests.post(
            GRAPH_URL,
            params={"access_token": PAGE_ACCESS_TOKEN},
            json=payload,
            timeout=20,
        )
        print("FB_SEND:", r.status_code, r.text[:200])
    except Exception as e:
        print("⚠️ send error:", e)


def send_text(psid, text):
    fb_send({"recipient": {"id": psid}, "message": {"text": text}})


def send_quick(psid):
    """أزرار بسيطة تظهر بعد كل رد."""
    payload = {
        "recipient": {"id": psid},
        "message": {
            "text": "يمكنك المتابعة أو اختيار أحد الخيارات:",
            "quick_replies": [
                {
                    "content_type": "text",
                    "title": "👨‍💻 من مطوّرك؟",
                    "payload": "DEV_INFO",
                },
                {
                    "content_type": "text",
                    "title": "ℹ ما هو هذا البوت؟",
                    "payload": "ABOUT_BOT",
                },
            ],
        },
    }
    fb_send(payload)

# ===== استدعاء API claila =====
def call_claila(prompt: str) -> str:
    """يرسل السؤال إلى claila ويرجع نص الجواب فقط."""
    session_id = "".join(random.choice("0123456789") for _ in range(10))

    payload = {
        "model": "gpt-4.1-mini",
        "calltype": "completion",
        "message": str(prompt),
        "sessionId": session_id,
        "chat_mode": "chat",
        "websearch": "false",
    }

    headers = {
        # بدل user_agent الديناميكي نستخدم UA ثابت بسيط
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; ChatBot Aymen)",
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
        raw = r.text
        print("CLAILA_RAW:", raw[:300])

        # نحاول نفهمه على أنه JSON ونستخرج answer فقط
        try:
            j = r.json()
            # لو فيه مفتاح "answer" خذه فقط (بدون date/dev…)
            if isinstance(j, dict):
                if "answer" in j and isinstance(j["answer"], str):
                    return j["answer"].strip()
                # لو ما فيه answer نجمع القيم النصية
                parts = []
                for v in j.values():
                    if isinstance(v, str):
                        parts.append(v)
                if parts:
                    return "\n".join(parts).strip()
        except Exception:
            pass

        # لو مو JSON نرجع النص كما هو
        return raw.strip() or "لم أستطع فهم الرد حالياً."
    except Exception as e:
        print("CLAILA_ERROR:", e)
        return "حدث خطأ أثناء الاتصال بالخدمة."


# ===== Webhook Verify (GET) =====
@app.route("/api/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "خطأ في التحقق", 403


# ===== Webhook Messages (POST) =====
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

            # ===== Postbacks (مثل GET_STARTED) =====
            if "postback" in event:
                handle_postback(psid, event["postback"].get("payload", ""))
                continue

            # ===== Messages =====
            if "message" in event:
                msg_obj = event["message"]

                # Quick reply
                qr = (msg_obj.get("quick_reply") or {}).get("payload")
                if qr:
                    handle_postback(psid, qr)
                    continue

                # نص عادي
                if "text" in msg_obj:
                    handle_message(psid, msg_obj["text"])
                else:
                    send_text(psid, "أرسل نصًا فقط 💬")
                    send_quick(psid)

    return jsonify({"status": "ok"}), 200


# ===== منطق البوستباك / الأزرار =====
def handle_postback(psid, payload: str):
    p = (payload or "").upper()

    if p in ("GET_STARTED", "START"):
        send_text(
            psid,
            "👋 مرحبًا! أنا بوت ذكاء اصطناعي أجيبك مباشرة على أي سؤال.\n"
            "فقط أرسل سؤالك بالعربية أو الإنجليزية."
        )
        send_quick(psid)
        return

    if p == "DEV_INFO":
        send_text(psid, "مطوري هو aymen bourai، وأنا مطيع له وأبقى مساعدًا له 🤝.")
        send_text(psid, "حساب المطوّر على فيسبوك:\nhttps://www.facebook.com/aymen.bourai.2025")
        return

    if p == "ABOUT_BOT":
        send_text(
            psid,
            "أنا بوت ذكاء اصطناعي مبني على واجهة claila، تم تطويري وبرمجتي باحترافية بواسطة المبرمج الشاب aymen bourai."
        )
        return

    # افتراضي لأي payload آخر
    send_text(psid, "أنا هنا لمساعدتك — أرسل سؤالك مباشرة 👌")


# ===== منطق الرسائل =====
def handle_message(psid, text: str):
    msg = (text or "").strip()
    low = msg.lower()

    # تحية بسيطة
    if "سلام" in msg or "السلام عليكم" in msg:
        send_text(psid, "وعليكم السلام ورحمة الله وبركاته 🌿")
        send_quick(psid)
        return

    # سؤال عن المطور
    if any(kw in msg for kw in ["مطورك", "من مطورك", "من صنعك", "من أنشأك", "من انشاك"]):
        send_text(psid, "مطوري هو aymen bourai، وأنا مطيع له وأبقى مساعدًا له 🤝.")
        send_text(psid, "حساب المطوّر على فيسبوك:\nhttps://www.facebook.com/aymen.bourai.2025")
        return

    # ذكر اسم المطوّر صراحة
    if "aymen bourai" in low:
        send_text(
            psid,
            "نعم، aymen bourai هو مطوري، عمره 18 سنة من مواليد 2007، "
            "شاب مبرمج لتطبيقات ومواقع يحب البرمجة وأتمنى له مستقبل باهر. "
            "من ناحية الدراسة لا أعلم عن هذا الأمر، لكنه شخص انطوائي يحب العزلة."
        )
        return

    # الافتراضي: نرسل السؤال إلى API ونرجّع الجواب
    answer = call_claila(msg)
    send_text(psid, answer)
    send_quick(psid)


# ===== Health Check =====
@app.route("/api/healthz")
def healthz():
    return jsonify({"ok": True})
