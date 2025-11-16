# api/index.py
from flask import Flask, request, jsonify
import os
import requests
import html
import time
import threading

app = Flask(__name__)

# المتغيرات البيئية (اضعها في Vercel)
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN", "")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "boykta2023")

# روابط الـ APIs
GPT_API_BASE = "https://vetrex.x10.mx/api/gpt4.php?text="
SORA_API_BASE = "https://vetrex.x10.mx/api/sora.php?prompt="

# نصوص خاصة بالمطور
AYMEN_PROFILE_TEXT = (
    "نعم aymen bourai هو مطوري.\n"
    "عمره 18 سنة (مواليد 2007).\n"
    "مبرمج تطبيقات ومواقع ويحب البرمجة.\n"
    "أتمنى له مستقبل باهر."
)
DEVELOPER_TEXT = "aymen bourai هو مطوري وانا مطيع له وابقا مساعد له."

GRAPH_API_URL = "https://graph.facebook.com/v17.0/me/messages"
PROFILE_API_URL = "https://graph.facebook.com/v17.0/me/messenger_profile"

# حالة مؤقتة للمستخدمين ينتظرون Prompt للفيديو
# صيغة: { psid: {"waiting_for_video": True, "since": timestamp} }
awaiting_video_prompt = {}

# --- Helpers
def send_message(psid, text):
    """إرسال رسالة نصية للمستخدم (نص فقط)."""
    if not PAGE_ACCESS_TOKEN:
        print("ERROR: PAGE_ACCESS_TOKEN not set")
        return
    payload = {"recipient": {"id": psid}, "message": {"text": text}}
    try:
        r = requests.post(GRAPH_API_URL, params={"access_token": PAGE_ACCESS_TOKEN}, json=payload, timeout=10)
        if r.status_code >= 400:
            print("Send message failed:", r.status_code, r.text)
    except Exception as e:
        print("Send message exception:", e)

def send_button_template(psid, text, buttons):
    """إرسال قالب زرّ (button template)."""
    if not PAGE_ACCESS_TOKEN:
        print("ERROR: PAGE_ACCESS_TOKEN not set")
        return
    payload = {
        "recipient": {"id": psid},
        "message": {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "button",
                    "text": text,
                    "buttons": buttons
                }
            }
        }
    }
    try:
        r = requests.post(GRAPH_API_URL, params={"access_token": PAGE_ACCESS_TOKEN}, json=payload, timeout=10)
        if r.status_code >= 400:
            print("Send button failed:", r.status_code, r.text)
    except Exception as e:
        print("Send button exception:", e)

def cleanup_awaiting_states(timeout_seconds=300):
    """احذف حالات الانتظار الأقدم من timeout_seconds لتجنب تسرب الذاكرة."""
    now = time.time()
    to_remove = [psid for psid, st in awaiting_video_prompt.items() if now - st.get("since", 0) > timeout_seconds]
    for psid in to_remove:
        awaiting_video_prompt.pop(psid, None)

# --- إعداد ملف الماسنجر (Get Started + Persistent Menu)
def set_messenger_profile():
    """يحاول تهيئة Get Started و Persistent Menu على صفحة الفيسبوك."""
    if not PAGE_ACCESS_TOKEN:
        print("Cannot set messenger profile: PAGE_ACCESS_TOKEN missing.")
        return
    payload = {
        "get_started": {"payload": "GET_STARTED_PAYLOAD"},
        "persistent_menu": [
            {
                "locale": "default",
                "composer_input_disabled": False,
                "call_to_actions": [
                    {"type": "postback", "title": "إنشاء فيديو", "payload": "CREATE_VIDEO_PAYLOAD"},
                    {"type": "postback", "title": "اسأل نصاً", "payload": "ASK_TEXT_PAYLOAD"},
                    {"type": "postback", "title": "معلومات", "payload": "INFO_PAYLOAD"}
                ]
            }
        ]
    }
    try:
        r = requests.post(PROFILE_API_URL, params={"access_token": PAGE_ACCESS_TOKEN}, json=payload, timeout=10)
        print("set_messenger_profile:", r.status_code, r.text)
    except Exception as e:
        print("set_messenger_profile exception:", e)

# نطلق الدالة في Thread عند بدء التطبيق (مرة واحدة)
def start_profile_setup_thread():
    try:
        t = threading.Thread(target=set_messenger_profile, daemon=True)
        t.start()
    except Exception as e:
        print("Could not start profile setup thread:", e)

start_profile_setup_thread()

# --- Webhook endpoints
@app.route("/api/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    challenge = request.args.get("hub.challenge")
    token = request.args.get("hub.verify_token")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Verification token mismatch", 403

@app.route("/api/webhook", methods=["POST"])
def webhook():
    # نظف الحالات القديمة
    cleanup_awaiting_states()

    data = request.get_json(silent=True)
    if not data:
        return "No payload", 400
    if data.get("object") != "page":
        return "Ignored", 200

    for entry in data.get("entry", []):
        for messaging in entry.get("messaging", []):
            # تجنب الرد على أحداث ليست من المستخدم أو ردود البوت نفسه
            message_obj = messaging.get("message", {})
            # إذا هذه حدث echo من بوتنا نفسه، تجاهله
            if message_obj and message_obj.get("is_echo"):
                # تجاهل رسائل الـ echo
                continue

            sender = messaging.get("sender", {}).get("id")
            if not sender:
                continue

            # تعامل مع postback (Get Started + أزرار)
            if messaging.get("postback"):
                payload = messaging["postback"].get("payload", "")
                if payload == "GET_STARTED_PAYLOAD":
                    buttons = [
                        {"type": "postback", "title": "إنشاء فيديو", "payload": "CREATE_VIDEO_PAYLOAD"},
                        {"type": "postback", "title": "اسأل نصاً", "payload": "ASK_TEXT_PAYLOAD"}
                    ]
                    send_button_template(sender, "أهلاً! اختر ما تريد أو أرسل نصاً:", buttons)
                    continue
                if payload == "CREATE_VIDEO_PAYLOAD":
                    awaiting_video_prompt[sender] = {"waiting_for_video": True, "since": time.time()}
                    send_message(sender, "ممتاز — ما هو موضوع الفيديو أو الوصف الذي تريده؟ أرسل سطرًا واحدًا لوصف الـ prompt.")
                    continue
                if payload == "ASK_TEXT_PAYLOAD":
                    send_message(sender, "أرسل النص الذي تريدني أن أجيبه.")
                    continue
                if payload == "INFO_PAYLOAD":
                    send_message(sender, "أنا بوت رد آلي. أرسل نصاً وسأجيبك بنص واضح.")
                    continue

            # message handling
            message = message_obj  # already fetched

            # attachments (صور/ميديا)
            if message.get("attachments"):
                send_message(sender, "✨ تم استلام المرفق. أرسل نصاً إن أردت ردًا نصيًّا.")
                continue

            # reaction (إن وُجد) — ملاحظة: تحتاج الاشتراك في messaging_reactions
            if messaging.get("reaction"):
                send_message(sender, "👋 أهلاً! كيف أساعدك اليوم؟")
                continue

            # quick_reply
            if message.get("quick_reply"):
                qr_payload = message["quick_reply"].get("payload", "")
                if qr_payload == "CREATE_VIDEO_PAYLOAD":
                    awaiting_video_prompt[sender] = {"waiting_for_video": True, "since": time.time()}
                    send_message(sender, "حسناً. أرسل وصف الفيديو الذي تريده الآن.")
                else:
                    send_message(sender, "تم استلام اختيارك.")
                continue

            # نص المستخدم
            if message.get("text"):
                raw_text = message.get("text", "").strip()
                text = raw_text.lower()

                # هل المستخدم في وضع انتظار prompt للفيديو؟
                if awaiting_video_prompt.get(sender, {}).get("waiting_for_video"):
                    awaiting_video_prompt.pop(sender, None)
                    send_message(sender, "جارٍ طلب إنشاء الفيديو... سأرسل الرد فورًا.")
                    try:
                        prompt = requests.utils.requote_uri(raw_text)
                        r = requests.get(SORA_API_BASE + prompt, timeout=15)
                        try:
                            j = r.json()
                        except Exception:
                            j = None

                        video_text = ""
                        if isinstance(j, dict):
                            video_resp = j.get("result") or j.get("response") or j.get("answer") or j.get("data") or ""
                            if isinstance(video_resp, (list, dict)):
                                video_resp = str(video_resp)
                            video_text = (video_resp or "").strip()
                        else:
                            video_text = html.unescape(r.text.strip())

                        if not video_text:
                            video_text = "تم إرسال طلب إنشاء الفيديو لكن لم يصلنا وصف واضح من الخادم."
                    except Exception as e:
                        print("SORA API error:", e)
                        video_text = "عذراً، لم أتمكن من الوصول لخدمة إنشاء الفيديو الآن. حاول لاحقًا."

                    send_message(sender, video_text)
                    continue

                # كلمات المطور المتعددة
                dev_keywords = [
                    "من قام بإنتاجك", "من مطورك", "من انتجك", "من صنعك",
                    "من أسسك", "من مصممك", "من قام بانتاجك"
                ]
                if any(kw in text for kw in dev_keywords):
                    send_message(sender, DEVELOPER_TEXT)
                    continue

                # اسم aymen
                if "aymen bourai" in text or "aymen" in text:
                    send_message(sender, AYMEN_PROFILE_TEXT)
                    continue

                # طلب إلى GPT API (نستخرج 'answer' فقط إن وُجد)
                try:
                    query = requests.utils.requote_uri(raw_text)
                    resp = requests.get(GPT_API_BASE + query, timeout=10)
                    try:
                        j = resp.json()
                    except Exception:
                        j = None

                    ans = ""
                    if isinstance(j, dict):
                        ans = j.get("answer") or j.get("response") or j.get("result") or ""
                        if isinstance(ans, (list, dict)):
                            ans = str(ans)
                        ans = (ans or "").strip()
                    else:
                        ans = html.unescape(resp.text.strip())

                    if not ans:
                        ans = "عذرًا، لم يصلني جواب واضح."
                except Exception as e:
                    print("GPT API error:", e)
                    ans = "عذراً، الخدمة غير متاحة حالياً."

                send_message(sender, ans)
                continue

            # حالة افتراضية محايدة
            send_message(sender, "أرسل رسالة نصية فقط.")
    return "EVENT_RECEIVED", 200

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "bot running"}), 200

if __name__ == "__main__":
    app.run(debug=True, port=3000)
