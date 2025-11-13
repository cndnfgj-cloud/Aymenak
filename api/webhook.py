from http.server import BaseHTTPRequestHandler
import json
import os
import requests
from urllib.parse import urlparse, parse_qs, quote_plus

PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
FB_API_URL = "https://graph.facebook.com/v18.0/me/messages"


def generate_reply(user_text: str) -> str:
    """
    توليد الرد على رسالة المستخدم.
    هنا نضيف الردود الخاصة و إلا نستدعي API الخارجية.
    """
    if not user_text:
        return "مرحباً، أرسل لي أي سؤال وسأحاول مساعدتك 😊"

    text = user_text.strip()
    lower = text.lower()

    # رد خاص على سؤال: من قام بإنتاجك
    if "من قام بإنتاجك" in text or "من قام بانتاجك" in text:
        return "aymen bourai هو مطوري وانا مطيع له وابقى مساعداً له."

    # رد خاص على: aymen bourai
    if "aymen bourai" in lower:
        return (
            "نعم aymen bourai هو مطوري، عمره 18 سنة من مواليد 2007، "
            "شاب مبرمج لتطبيقات ومواقع يحب البرمجة، وشخص انطوائي يحب العزلة، "
            "وأتمنى له مستقبلاً باهراً 🌟"
        )

    # استدعاء API الخارجية
    try:
        url = "https://vetrex.x10.mx/api/gpt4.php?text=" + quote_plus(text)
        resp = requests.get(url, timeout=40)
        resp.raise_for_status()
        content = resp.text.strip()
        if not content:
            return "لم أستقبل رداً من خدمة الذكاء الاصطناعي الخارجية، حاول مرة أخرى."
        return content
    except Exception:
        return "حدث خطأ أثناء الاتصال بواجهة الذكاء الاصطناعي الخارجية. حاول مرة أخرى لاحقاً."


def send_message(recipient_id: str, message_text: str) -> None:
    """
    إرسال رسالة نصية إلى مستخدم ماسنجر.
    البوت فقط يجيب نصياً بدون أزرار أو قوالب.
    """
    if not PAGE_ACCESS_TOKEN:
        # لو نسيت تضيف التوكن في Vercel البوت لن يستطيع الرد
        return

    payload = {
        "recipient": {"id": recipient_id},
        "messaging_type": "RESPONSE",
        "message": {"text": message_text},
    }
    params = {"access_token": PAGE_ACCESS_TOKEN}

    try:
        requests.post(FB_API_URL, params=params, json=payload, timeout=20)
    except Exception:
        # نتجاهل الأخطاء حتى لا نكسر الرد على فيسبوك
        pass


class handler(BaseHTTPRequestHandler):
    """
    Webhook فيسبوك ماسنجر ليعمل على Vercel (Python Runtime).
    - GET: لتأكيد الـ webhook (verify token)
    - POST: لاستقبال رسائل المستخدمين والرد عليهم
    """

    def _send_json(self, status=200, data=None):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        if data is not None:
            self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_GET(self):
        # تأكيد Webhook من فيسبوك
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        mode = query.get("hub.mode", [None])[0]
        token = query.get("hub.verify_token", [None])[0]
        challenge = query.get("hub.challenge", [None])[0]

        if mode == "subscribe" and token == VERIFY_TOKEN and challenge:
            # فيسبوك يتوقع أن نطبع الـ challenge كما هو
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(challenge.encode("utf-8"))
        else:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Forbidden")

    def do_POST(self):
        # استقبال events من ماسنجر
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        try:
            data = json.loads(body.decode("utf-8"))
        except Exception:
            return self._send_json(400, {"error": "invalid_json"})

        if data.get("object") != "page":
            return self._send_json(404, {"error": "not_a_page_event"})

        for entry in data.get("entry", []):
            for event in entry.get("messaging", []):
                sender_id = event.get("sender", {}).get("id")

                # لو كانت رسالة نصية عادية
                if "message" in event and "text" in event["message"]:
                    user_text = event["message"]["text"]
                    reply = generate_reply(user_text)
                    if sender_id and reply:
                        send_message(sender_id, reply)

                # لو كان Postback (مثل زر Get Started) نتعامل معه كرسالة ترحيب
                elif "postback" in event:
                    if sender_id:
                        welcome = (
                            "مرحباً! أنا بوت مبني على API خارجي.\n"
                            "اسألني أي شيء وسأحاول مساعدتك مباشرة بدون الحاجة للضغط على زر بدء الاستخدام 🤖"
                        )
                        send_message(sender_id, welcome)

        return self._send_json(200, {"status": "ok"})
