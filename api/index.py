from flask import Flask, request
import requests
import json
import os
from datetime import datetime, timedelta, timezone
from dateutil import parser

app = Flask(__name__)

# ===========================================================
# إعدادات البوت والتوكنات
# ===========================================================

# رمز التحقق للويب هوك
VERIFY_TOKEN = "boykta 2023"

# توكن صفحة الفيسبوك (يفضل وضعه في Environment Variables)
PAGE_ACCESS_TOKEN = os.environ.get('FB_PAGE_ACCESS_TOKEN', 'ضع_توكن_الصفحة_هنا_اذا_لم_تستخدم_ENV')

# إعدادات Vulcan API (من كودك الأصلي)
DEVICE_ID = "B4A13AE09F22A2A4"
MAX_CHAT_HISTORY = 20 # تم تقليله قليلاً لتسريع المعالجة في vercel
MAX_TOKENS = 0

# ذاكرة مؤقتة للمحادثات والتوكن (ملاحظة: في vercel قد يتم تصفيرها عند إعادة تشغيل الخادم)
user_chats = {}
access_token_data = {"token": "", "expiry": datetime.now(timezone.utc)}

# ===========================================================
# دوال Vulcan API (كما هي مع تعديلات طفيفة)
# ===========================================================

def get_access_token(force_refresh=False):
    global access_token_data
    # التحقق من صلاحية التوكن الحالي
    if not force_refresh and access_token_data["token"] and access_token_data["expiry"] > datetime.now(timezone.utc):
        return access_token_data["token"]

    url = "https://api.vulcanlabs.co/smith-auth/api/v1/token"
    payload = {"device_id": DEVICE_ID, "order_id": "", "product_id": "", "purchase_token": "", "subscription_id": ""}
    headers = {
        "User-Agent": "Chat Smith Android, Version 4.0.5(1032)",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "x-vulcan-application-id": "com.smartwidgetlabs.chatgpt",
        "x-vulcan-request-id": "9149487891757687027212"
    }
    try:
        # تقليل المهلة لتناسب Vercel
        response = requests.post(url, json=payload, headers=headers, timeout=9)
        data = response.json()
        token = data.get("AccessToken", "")
        expiry_str = data.get("AccessTokenExpiration")
        if expiry_str:
            expiry = parser.isoparse(expiry_str)
        else:
            expiry = datetime.now(timezone.utc) + timedelta(minutes=30)
        access_token_data = {"token": token, "expiry": expiry}
        return token
    except Exception as e:
        print(f"Token Error: {e}")
        return ""

def query_vulcan(token, messages):
    url = "https://api.vulcanlabs.co/smith-v2/api/v7/chat_android"
    payload = {
        "model": "gpt-4o-mini",
        "user": DEVICE_ID,
        "messages": messages,
        "max_tokens": MAX_TOKENS,
        "nsfw_check": True
    }
    headers = {
        "User-Agent": "Chat Smith Android, Version 4.0.5(1032)",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "x-auth-token": token,
        "authorization": f"Bearer {token}",
        "x-vulcan-application-id": "com.smartwidgetlabs.chatgpt",
        "x-vulcan-request-id": "9149487891757687028153"
    }
    try:
        # Vercel لديه مهلة 10 ثواني، نجعل الطلب 8 ثواني لنتجنب قتل العملية
        response = requests.post(url, json=payload, headers=headers, timeout=8)
        if response.status_code == 200:
            data = response.json()
            return data["choices"][0]["Message"]["content"]
        else:
            return f"Error from API: {response.status_code}"
    except Exception as e:
        print(f"Vulcan Chat Error: {e}")
        return "عذراً، الخادم مشغول حالياً."

# ===========================================================
# دوال فيسبوك
# ===========================================================

def send_facebook_message(recipient_id, text):
    params = {"access_token": PAGE_ACCESS_TOKEN}
    headers = {"Content-Type": "application/json"}
    data = {
        "recipient": {"id": recipient_id},
        "message": {"text": text}
    }
    # استخدام Graph API
    requests.post("https://graph.facebook.com/v19.0/me/messages", params=params, headers=headers, json=data)

# ===========================================================
# Webhook Route
# ===========================================================

@app.route('/', methods=['GET', 'POST'])
def webhook():
    # 1. التحقق (Verification)
    if request.method == 'GET':
        if request.args.get('hub.mode') == 'subscribe' and request.args.get('hub.verify_token') == VERIFY_TOKEN:
            return request.args.get('hub.challenge'), 200
        return "Verification failed", 403

    # 2. استقبال الرسائل (Handling Messages)
    if request.method == 'POST':
        try:
            data = request.json
            if data.get('object') == 'page':
                for entry in data.get('entry', []):
                    for event in entry.get('messaging', []):
                        sender_id = event['sender']['id']

                        # --- التعامل مع زر البدء (Postback) ---
                        if 'postback' in event:
                            payload = event['postback'].get('payload')
                            if payload == 'GET_STARTED' or payload == 'STARTED':
                                welcome_msg = "أهلاً بك! أنا بوت ذكي مطيع للمطور aymen bourai. اسألني أي سؤال."
                                send_facebook_message(sender_id, welcome_msg)
                            continue # ننتقل للحدث التالي

                        # --- التعامل مع الرسائل النصية ---
                        if 'message' in event and 'text' in event['message']:
                            user_text = event['message']['text']
                            
                            # 1. المنطق الخاص بالمطور
                            lower_text = user_text.lower()
                            response_text = ""

                            if "aymen bourai" in lower_text:
                                response_text = "نعم aymen bourai هو مطوري عمره 18 سنة من مواليد 2007 شخص شاب مبرمج لتطبيقات ومواقع يحب البرمجة واتمنى له مستقبل باهر من ناحية الدراسة لاأعلم عن هذا امر لكنه شخص انطوائي يحب العزلة"
                            
                            elif "من قام بإنتاجك" in lower_text or "من مطورك" in lower_text or "من صنعك" in lower_text:
                                response_text = "aymen bourai هو مطوري وانا مطيع له وابقا مساعد له."
                            
                            # 2. المنطق الخاص بالذكاء الاصطناعي (Vulcan)
                            else:
                                # جلب التوكن
                                token = get_access_token()
                                if not token:
                                    send_facebook_message(sender_id, "فشل الاتصال بخادم المصادقة.")
                                    continue

                                # إدارة سجل المحادثة (بسيط)
                                if sender_id not in user_chats:
                                    user_chats[sender_id] = []
                                
                                # إضافة رسالة المستخدم
                                user_chats[sender_id].append({"role": "user", "content": user_text})
                                
                                # قص السجل إذا كان طويلاً
                                if len(user_chats[sender_id]) > MAX_CHAT_HISTORY:
                                    user_chats[sender_id] = user_chats[sender_id][-MAX_CHAT_HISTORY:]

                                # جلب الرد
                                ai_response = query_vulcan(token, user_chats[sender_id])
                                
                                # إضافة رد البوت للسجل
                                user_chats[sender_id].append({"role": "assistant", "content": ai_response})
                                response_text = ai_response

                            # إرسال الرد النهائي
                            send_facebook_message(sender_id, response_text)

            return "EVENT_RECEIVED", 200
        except Exception as e:
            print(f"Error: {e}")
            return "Error", 500

    return "Hello World", 200
