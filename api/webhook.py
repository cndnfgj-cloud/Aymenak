from http.server import BaseHTTPRequestHandler
import json
import os
import requests
import random
from urllib.parse import urlparse, parse_qs


PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "boykta 2023")

FB_API = "https://graph.facebook.com/v18.0/me/messages"


# ============================
# 1 — استدعاء API Claila
# ============================

def ask_claila(text: str) -> str:
    url = "https://app.claila.com/api/v2/unichat2"

    payload = {
        'model': "gpt-4.1-mini",
        'calltype': "completion",
        'message': text,
        'sessionId': "".join(random.choice("0123456789") for _ in range(10)),
        'chat_mode': "chat",
        'websearch': "false"
    }

    headers = {
        'User-Agent': "Mozilla/5.0",
        'origin': "https://app.claila.com",
        'referer': "https://app.claila.com/chat",
        'accept-language': "ar",
        'x-requested-with': "XMLHttpRequest"
    }

    try:
        resp = requests.post(url, data=payload, headers=headers, timeout=30)
        data = resp.json()

        # نرجع الرد فقط
        return data.get("reply", "لم يصل رد من الخادم..")

    except Exception:
        return "حدث خطأ أثناء الاتصال بالخادم."


# ============================
# 2 — منطق الرد الخاص بك
# ============================

def generate_reply(user_text: str) -> str:
    text = user_text.strip()
    lower = text.lower()

    # أسئلة عن المطور
    dev_questions = [
        "من مطورك", "من مبرمجك", "من انشأك", "من صممك",
        "من أنتجك", "من قام ببرمجتك", "من صنعك"
    ]

    if any(q in text for q in dev_questions):
        return "aymen bourai هو مبرمجي، لكني مجرد ذكاء اصطناعي مساعد له 😊"

    if "aymen bourai" in lower:
        return (
            "نعم aymen bourai هو مطوري، عمره 18 سنة من مواليد 2007، "
            "شاب مبرمج لتطبيقات ومواقع يحب البرمجة، وشخص انطوائي يحب العزلة، "
            "وأتمنى له مستقبلاً باهراً 🌟"
        )

    # غير ذلك → سؤال للذكاء الاصطناعي
    return ask_claila(text)


# ============================
# 3 — إرسال رسالة لماسنجر
# ============================

def send_msg(user_id: str, message: str):
    if not PAGE_ACCESS_TOKEN:
        return

    payload = {
        "recipient": {"id": user_id},
        "message": {"text": message},
        "messaging_type": "RESPONSE"
    }

    params = {"access_token": PAGE_ACCESS_TOKEN}

    requests.post(FB_API, params=params, json=payload)


# ============================
# 4 — Webhook Handler
# ============================

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # فيسبوك يطلب Verify Token
        query = parse_qs(urlparse(self.path).query)

        mode = query.get("hub.mode", [""])[0]
        token = query.get("hub.verify_token", [""])[0]
        challenge = query.get("hub.challenge", [""])[0]

        if mode == "subscribe" and token == VERIFY_TOKEN:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(challenge.encode())
        else:
            self.send_response(403)
            self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        data = json.loads(body.decode())

        if data.get("object") != "page":
            return

        for entry in data.get("entry", []):
            for event in entry.get("messaging", []):

                sender = event.get("sender", {}).get("id")

                # رسالة نصية مباشرة
                if "message" in event and "text" in event["message"]:
                    txt = event["message"]["text"]
                    reply = generate_reply(txt)
                    send_msg(sender, reply)

                # postback (زر بدء الاستخدام)
                elif "postback" in event:
                    payload = event["postback"].get("payload", "")
                    reply = generate_reply(payload or "مرحبا")
                    send_msg(sender, reply)

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')
