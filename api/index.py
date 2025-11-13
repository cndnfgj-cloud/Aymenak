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


# ===== إرسال رسالة لفيسبوك =====
def fb_send(payload):
    if not PAGE_ACCESS_TOKEN:
        print("❌ PAGE_ACCESS_TOKEN مفقود! أضفه في إعدادات Vercel.")
        return
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


# ===== استدعاء claila =====
def call_claila(prompt: str) -> str:
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

        # نحاول نفهمه JSON ونجيب الحقل "answer" لو موجود
        try:
            j = r.json()
            if isinstance(j, dict) and isinstance(j.get("answer"), str):
                return j["answer"].strip()
        except Exception:
            pass

        return raw.strip() or "لم أستطع فهم الرد حالياً."
    except Exception as e:
        print("CLAILA_ERROR:", e)
        return "حدث خطأ أثناء الاتصال بخدمة الذكاء الاصطناعي."


# ===== Healthz =====
@app.route("/api/healthz")
def healthz():
    return jsonify({"ok": True})


# ===== Webhook Verify (GET) =====
@app.route("/api/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    print("VERIFY_HIT:", mode, token)

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "خطأ في التحقق", 403


# ===== Webhook Messages (POST) =====
@app.route("/api/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True) or {}
    print("WEBHOOK_EVENT:", json.dumps(data)[:500])

    if data.get("object") != "page":
        return jsonify({"status": "ignored"}), 200

    for entry in data.get("entry", []):
        for event in entry.get("messaging", []):
            psid = event.get("sender", {}).get("id")
            if not psid:
                continue

            # POSTBACK (مثل GET_STARTED)
            if "postback" in event:
                payload = event["postback"].get("payload", "")
                handle_postback(psid, payload)
                continue

            # رسالة عادية
            if "message" in event and "text" in event["message"]:
                msg_text = event["message"]["text"]
                handle_message(psid, msg_text)

    return jsonify({"status": "ok"}), 200


# ===== التعامل مع الأزرار / POSTBACK =====
def handle_postback(psid, payload: str):
    p = (payload or "").upper()
    print("POSTBACK:", psid, p)

    if p in ("GET_STARTED", "START"):
        send_text(
            psid,
            "👋 مرحبًا! أنا بوت ذكاء اصطناعي من تطوير aymen bourai.\n"
            "فقط أرسل سؤالك وسأجيبك مباشرة."
        )
        return

    send_text(psid, "أرسل سؤالك في رسالة نصية وسأحاول مساعدتك.")


# ===== منطق الرسائل =====
def handle_message(psid, text: str):
    msg = (text or "").strip()
    low = msg.lower()
    print("MSG_FROM:", psid, "TEXT:", msg)

    # تحية
    if "سلام" in msg or "السلام عليكم" in msg:
        send_text(psid, "وعليكم السلام ورحمة الله وبركاته 🌿")
        return

    # المطور
    if any(kw in msg for kw in ["مطورك", "من مطورك", "من صنعك", "من أنشأك", "من انشاك"]):
        send_text(psid, "مطوري هو aymen bourai، وأنا مطيع له وأبقى مساعدًا له 🤝.")
        send_text(psid, "حساب المطوّر على فيسبوك:\nhttps://www.facebook.com/aymen.bourai.2025")
        return

    if "aymen bourai" in low:
        send_text(
            psid,
            "نعم، aymen bourai هو مطوري، عمره 18 سنة من مواليد 2007، "
            "شاب مبرمج لتطبيقات ومواقع يحب البرمجة وأتمنى له مستقبل باهر. "
            "من ناحية الدراسة لا أعلم عن هذا الأمر، لكنه شخص انطوائي يحب العزلة."
        )
        return

    # الافتراضي: إرسل السؤال للـ API
    answer = call_claila(msg)
    send_text(psid, answer)


# نقطة دخول عادية (اختيارية للاختبار)
@app.route("/")
def root():
    return "Facebook bot is running.", 200
