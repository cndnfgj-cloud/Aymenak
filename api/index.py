import os
import re
import json
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ======== CONFIG ========
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "boykta 2023")
GRAPH_URL = "https://graph.facebook.com/v17.0/me/messages"

SESSION_MODE = {}   # 1 = AI , 2 = IMAGE

# ======== FACEBOOK SEND ========
def fb_send(payload):
    try:
        requests.post(
            GRAPH_URL,
            params={"access_token": PAGE_ACCESS_TOKEN},
            json=payload,
            timeout=15
        )
    except Exception as e:
        print("Send Error:", e)


def send_text(psid, text):
    fb_send({"recipient": {"id": psid}, "message": {"text": text}})


# ======== AI MODE (DeepSeek Chat) ========
def deepseek_get_nonce():
    try:
        r = requests.get("https://chat-deep.ai/", headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if r.status_code != 200:
            return None
        patterns = [
            r'"nonce":"([a-f0-9]+)"',
            r'nonce["\']?\s*:\s*["\']([a-f0-9]+)["\']'
        ]
        for pat in patterns:
            m = re.search(pat, r.text)
            if m:
                return m.group(1)
        return None
    except:
        return None


def deepseek_reply(msg):
    nonce = deepseek_get_nonce()
    if not nonce:
        return "تعذر الحصول على رد الآن."

    url = "https://chat-deep.ai/wp-admin/admin-ajax.php"
    payload = {
        "action": "deepseek_chat",
        "message": msg,
        "model": "deepseek-chat",
        "nonce": nonce,
        "save_conversation": "0",
        "session_only": "1"
    }
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Origin": "https://chat-deep.ai",
        "Referer": "https://chat-deep.ai/",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    try:
        r = requests.post(url, data=payload, headers=headers, timeout=25)
        j = r.json()
        if j.get("success"):
            resp = j["data"]["response"]
            return clean_reply(resp)
        return "لم أفهم، أعد صياغة سؤالك."
    except:
        return "حدث خطأ أثناء الاتصال بالخدمة."


# ======== IMAGE MODE ========
def generate_image(text):
    try:
        url = f"https://sii3.top/api/imagen-3.php?text={text}&aspect_ratio=1:1&style=Auto"
        r = requests.get(url, timeout=20).json()
        return r["image"]
    except:
        return None


# ======== CLEANING ========
BAD = re.compile(
    r"(date|answer|dev|dont\s*forget|support\s*the\s*channel)", re.I
)
WS = re.compile(r"\s+")


def clean_reply(text):
    text = BAD.sub("", text)
    text = re.sub(r"http\S+|www\S+|@\S+", "", text)
    text = text.replace("{", "").replace("}", "").replace(":", " ")
    text = WS.sub(" ", text).strip()
    return text


# ======== WEBHOOK VERIFY ========
@app.route("/api/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Verification failed", 403


# ======== MAIN WEBHOOK ========
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

            # ===== START BUTTON =====
            if "postback" in event:
                payload = event["postback"].get("payload", "")
                if payload == "GET_STARTED":
                    send_text(psid, "مرحباً! اختر وضع التشغيل:\n1- ذكاء اصطناعي\n2- إنشاء صور")
                    return "ok", 200

            # ===== USER MESSAGE =====
            if "message" in event and "text" in event["message"]:
                msg = event["message"]["text"].strip()

                # اختيار وضع التشغيل
                if msg == "1":
                    SESSION_MODE[psid] = 1
                    send_text(psid, "تم تفعيل وضع الذكاء الاصطناعي 🤖.\nاسألني ما تريد!")
                    return "ok", 200

                if msg == "2":
                    SESSION_MODE[psid] = 2
                    send_text(psid, "تم تفعيل وضع إنشاء الصور 🖼️.\nارسل وصف الصورة الآن.")
                    return "ok", 200

                # مطورك؟
                if "مطورك" in msg or "من صنعك" in msg or "من انشاك" in msg:
                    send_text(psid, "مطوري هو aymen bourai، وأنا مساعده المطيع 🤝.")
                    return "ok", 200

                if "aymen bourai" in msg.lower():
                    send_text(psid, "نعم، aymen bourai هو مطوري. شاب موهوب من 2007 ويحب البرمجة ❤️.")
                    return "ok", 200

                # لم يحدد الوضع
                if psid not in SESSION_MODE:
                    send_text(psid, "اختر الوضع:\n1- ذكاء اصطناعي\n2- إنشاء صور")
                    return "ok", 200

                mode = SESSION_MODE[psid]

                # ===== AI MODE =====
                if mode == 1:
                    reply = deepseek_reply(msg)
                    send_text(psid, reply)
                    return "ok", 200

                # ===== IMAGE MODE =====
                if mode == 2:
                    image = generate_image(msg)
                    if image:
                        fb_send({
                            "recipient": {"id": psid},
                            "message": {
                                "attachment": {
                                    "type": "image",
                                    "payload": {"url": image}
                                }
                            }
                        })
                    else:
                        send_text(psid, "تعذر إنشاء الصورة.")
                    return "ok", 200

    return jsonify({"status": "ok"}), 200


@app.route("/api/healthz")
def health():
    return jsonify({"ok": True})
