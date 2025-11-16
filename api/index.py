# api/index.py
from flask import Flask, request, jsonify
import os
import requests
import html

app = Flask(__name__)

# اقرأ المتغيرات من بيئة Vercel (ضعها في Project → Settings → Environment Variables)
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN", "")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "boykta_2023")

# رابط الـ API الخارجي (أضف النص بعد = )
API_URL = "https://vetrex.x10.mx/api/gpt4.php?text="

# نصوص خاصة بالمطور
AYMEN_PROFILE_TEXT = (
    "نعم aymen bourai هو مطوري.\n"
    "عمره 18 سنة (مواليد 2007).\n"
    "مبرمج تطبيقات ومواقع ويحب البرمجة.\n"
    "أتمنى له مستقبل باهر. من ناحية الدراسة لست متأكداً، لكنه شخص انطوائي يحب العزلة."
)
DEVELOPER_TEXT = "aymen bourai هو مطوري وانا مطيع له وابقا مساعد له."

GRAPH_API_URL = "https://graph.facebook.com/v17.0/me/messages"


def send_message(psid, text):
    """إرسال رسالة نصية للمستخدم (text فقط)."""
    if not PAGE_ACCESS_TOKEN:
        print("ERROR: PAGE_ACCESS_TOKEN not set")
        return
    payload = {
        "recipient": {"id": psid},
        "message": {"text": text}
    }
    try:
        r = requests.post(GRAPH_API_URL, params={"access_token": PAGE_ACCESS_TOKEN}, json=payload, timeout=8)
        if r.status_code >= 400:
            print("Send message failed:", r.status_code, r.text)
    except Exception as e:
        print("Send message exception:", e)


@app.route("/api/webhook", methods=["GET"])
def verify():
    """Facebook webhook verification"""
    mode = request.args.get("hub.mode")
    challenge = request.args.get("hub.challenge")
    token = request.args.get("hub.verify_token")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Verification token mismatch", 403


@app.route("/api/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True)
    if not data:
        return "No payload", 400

    # فيسبوك يرسل object = "page" عادةً
    if data.get("object") != "page":
        return "Ignored", 200

    for entry in data.get("entry", []):
        for messaging in entry.get("messaging", []):
            sender = messaging.get("sender", {}).get("id")
            if not sender:
                continue

            # 1) رد عند وصول صورة أو مرفق
            message = messaging.get("message", {})
            if message and message.get("attachments"):
                # رسالة جاهزة عند استقبال صورة/ميديا
                send_message(sender, "✨ انا آسف، لا أملك حالياً ميزة قراءة الصور — المطور aymen يعمل على حل المشكلة قريباً.")
                continue

            # 2) رد على رد فعل (reaction) — تحتاج الاشتراك في messaging_reactions
            if messaging.get("reaction"):
                send_message(sender, "👋 أهلاً! مرحباً بك، اسألني أي شيء أو أرسل رسالة جميلة.")
                continue

            # 3) تعامل مع القصاصات السريعة quick_replies (لو أُرسلت)
            if message and message.get("quick_reply"):
                qr_payload = message["quick_reply"].get("payload", "")
                # يمكنك توسيع المعالجات هنا بناءً على payload
                if qr_payload == "ASK_MORE":
                    send_message(sender, "تفضل اسأل سؤالك التالي.")
                else:
                    send_message(sender, "شكراً! كيف أساعدك بعد؟")
                continue

            # 4) نص المستخدم
            if message and message.get("text"):
                raw_text = message.get("text", "").strip()
                text = raw_text.lower()

                # كلمات مفتاحية خاصة بالمطور (بصيغ متعددة)
                dev_keywords = [
                    "من قام بإنتاجك", "من مطورك", "من انتجك", "من صنعك", "من أسسك", "من مصممك",
                    "من قام بانتاجك", "من يفكرك", "who made you"
                ]
                # تحقق إن أي من المفردات موجودة في النص (بالعربية أو الإنجليزية المختصرة)
                if any(kw in text for kw in dev_keywords):
                    send_message(sender, DEVELOPER_TEXT)
                    continue

                # اسم أيمن أو aymen bourai
                if "aymen bourai" in text or "aymen" in text:
                    send_message(sender, AYMEN_PROFILE_TEXT)
                    continue

                # استعلام الـ API الخارجي: نحاول استخراج answer فقط
                try:
                    # هدّئ النص لاستبدال الفراغات بمقابل صالح في رابط
                    query = requests.utils.requote_uri(raw_text)
                    resp = requests.get(API_URL + query, timeout=8)
                    # حاول تحويل الرد ل JSON — إن لم يكن JSON نستخدم النص الخام
                    try:
                        j = resp.json()
                    except Exception:
                        # إن لم يكن JSON، حاول فك HTML entities ثم استخدم النص
                        safe = resp.text.strip()
                        safe = html.unescape(safe)
                        # أحيانًا API تعيد JSON داخل نص — حاول استخراج "answer"
                        # لكن بشكل افتراضي نرسل النص الخام
                        answer = safe if safe else "عذراً، لم أستلم رد صالح من الخادم."
                    if 'answer' in locals() and answer:
                        # وصلنا إجابة من الحالة السابقة (non-json)
                        pass
                    else:
                        # إذا واحد من الأساليب أعاد JSON حاول الحصول على 'answer'
                        if isinstance(j, dict):
                            answer = j.get("answer") or j.get("response") or j.get("result") or ""
                            if isinstance(answer, (list, dict)):
                                answer = str(answer)
                            answer = (answer or "").strip()
                        else:
                            answer = resp.text.strip()
                    # لو لا يوجد شيء معقول، نضع رسالة بديلة
                    if not answer:
                        answer = "عذراً، تعذّر الحصول على جواب واضح من الخادم."
                except Exception as e:
                    print("API call failed:", e)
                    answer = "عذراً، الخدمة غير متاحة حالياً. حاول لاحقاً."

                # أرسل النص النهائي للمستخدم (نص فقط)
                send_message(sender, answer)
                continue

            # إن لم يكن هناك شيء مفهوم
            send_message(sender, "لم أفهم رسالتك. أرسل نصاً لأجيبك أو اسأل عن المطور.")
    return "EVENT_RECEIVED", 200


@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "bot running"}), 200
