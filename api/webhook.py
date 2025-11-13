from http.server import BaseHTTPRequestHandler
import json
import os
import requests
from urllib.parse import urlparse, parse_qs

# توكن صفحة فيسبوك (من متغيرات البيئة في Vercel)
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")

# توكن تأكيد الويب هوك
# إذا لم تضبطه في Vercel سيستخدم القيمة الافتراضية "boykta 2023"
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "boykta 2023")

FB_API_URL = "https://graph.facebook.com/v18.0/me/messages"


def call_vetrex_api(user_text: str) -> str:
    """
    استدعاء API vetrex وإرجاع الرد فقط كنص.
    """
    base_url = "https://vetrex.x10.mx/api/gpt4.php"

    params = {
        "text": user_text,
        "prompt": "انا مطورك اسمي ديفل",
    }

    resp = requests.get(base_url, params=params, timeout=40)
    resp.raise_for_status()
    answer = resp.text.strip()

    if not answer:
        return "لم أستقبل أي رد من خدمة الذكاء الاصطناعي، حاول مرة أخرى."

    return answer


def generate_reply(user_text: str) -> str:
    """
    منطق تحديد الرد:
    - أسئلة عن المطوّر → رد خاص
    - كلمة 'aymen bourai' → سيرة ثابتة
    - غير ذلك → استدعاء VETREX API
    """
    if not user_text:
        return "مرحباً، أرسل لي أي سؤال وسأحاول مساعدتك 😊"

    text = user_text.strip()
    lower = text.lower()

    # أسئلة عن المطوّر / من أنشأك / من صمّمك...
    dev_questions = [
        "من مطورك",
        "من مبرمجك",
        "من صممك",
        "من انشأك",
        "من أنشأك",
        "من انتجك",
        "من أنتجك",
        "من قام ببرمجتك",
        "من صنعك",
    ]
    if any(q in text for q in dev_questions):
        return "aymen bourai هو مبرمجي، لكن أنا مجرد ذكاء اصطناعي مساعد له 😊"

    # ذكر الاسم مباشرة
    if "aymen bourai" in lower:
        return (
            "نعم aymen bourai هو مطوري، عمره 18 سنة من مواليد 2007، "
            "شاب مبرمج لتطبيقات ومواقع يحب البرمجة، وشخص انطوائي يحب العزلة، "
            "وأتمنى له مستقبلاً باهراً 🌟"
        )

    # باقي الأسئلة → نستخدم API vetrex
    try:
        return call_vetrex_api(text)
    except Exception:
        return "حدث خطأ أثناء الاتصال بواجهة الذكاء الاصطناعي الخارجية. حاول مرة أخرى لاحقاً."


def send_message(recipient_id: str, message_text: str) -> None:
    """
    إرسال رسالة نصية إلى مستخدم فيسبوك ماسنجر.
    """
    if not PAGE_ACCESS_TOKEN:
        # لو نسيت تضيف PAGE_ACCESS_TOKEN في Vercel، لن يرسل البوت أي شيء
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
        # نتجاهل الأخطاء هنا حتى لا نكسر الاستجابة للويب هوك
        pass


class handler(BaseHTTPRequestHandler):
    """
    Webhook فيسبوك ماسنجر ليعمل على Vercel (Python Runtime).
    - GET: لتأكيد الويب هوك (verify token)
    - POST: لاستقبال رسائل المستخدمين والرد عليها مباشرة
    """

    def _send_json(self, status=200, data=None):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        if data is not None:
            self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_GET(self):
        """
        فيسبوك يستعمل GET أول مرة لتأكيد الـ Webhook:
        /api/webhook?hub.mode=subscribe&hub.verify_token=...&hub.challenge=...
        """
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        mode = query.get("hub.mode", [None])[0]
        token = query.get("hub.verify_token", [None])[0]
        challenge = query.get("hub.challenge", [None])[0]

        if mode == "subscribe" and token == VERIFY_TOKEN and challenge:
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(challenge.encode("utf-8"))
        else:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Forbidden")

    def do_POST(self):
        """
        استقبال الأحداث من ماسنجر (رسائل، Postbacks، إلخ)
        هنا نتخطى موضوع زر "بدء الاستخدام" بالكامل:
        أي رسالة نصية من المستخدم → نرد عليها مباشرة.
        """
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

                # رسالة نصية من المستخدم
                if "message" in event and "text" in event["message"]:
                    user_text = event["message"]["text"]
                    reply = generate_reply(user_text)
                    if sender_id and reply:
                        send_message(sender_id, reply)

                # لو فيه postback (مثلاً من زر "Get Started") نعامله كنص بسيط
                elif "postback" in event:
                    payload = event["postback"].get("payload", "")
                    # نعتبر أن أي postback هو بداية محادثة
                    reply = generate_reply(payload or "مرحبا")
                    if sender_id and reply:
                        send_message(sender_id, reply)

        return self._send_json(200, {"status": "ok"})
