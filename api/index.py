from flask import Flask, request, jsonify
import requests
import random
import string
from user_agent import generate_user_agent
import os

app = Flask(__name__)

# ===========================================================
# إعدادات البوت (يجب عليك تعبئة رمز الوصول هنا أو في متغيرات البيئة)
# ===========================================================

# رمز التحقق الذي وضعته أنت
VERIFY_TOKEN = "boykta 2023"

# ضع هنا Page Access Token الخاص بصفحتك من فيسبوك
# يفضل وضعه في Environment Variables في Vercel باسم FB_PAGE_ACCESS_TOKEN
PAGE_ACCESS_TOKEN = os.environ.get('FB_PAGE_ACCESS_TOKEN', 'ضع_توكن_الصفحة_هنا_اذا_لم_تستخدم_ENV')

# ===========================================================
# دالة الاتصال بـ API الذكاء الاصطناعي (Claila)
# ===========================================================
def get_claila_ai_response(user_message):
    url = "https://app.claila.com/api/v2/unichat2"
    
    # توليد Session ID عشوائي كما في كودك
    session_id = "".join(random.choice("0123456789") for _ in range(10))
    
    payload = {
        'model': "gpt-4.1-mini",
        'calltype': "completion",
        'message': f'{user_message}',
        'sessionId': session_id,
        'chat_mode': "chat",
        'websearch': "false"
    }
    
    try:
        headers = {
            'User-Agent': generate_user_agent(),
            'sec-ch-ua-platform': '"Android"',
            'sec-ch-ua': '"Google Chrome";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
            'sec-ch-ua-mobile': '?1',
            'x-requested-with': 'XMLHttpRequest',
            'origin': 'https://app.claila.com',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-mode': 'cors',
            'sec-fetch-dest': 'empty',
            'referer': 'https://app.claila.com/chat?uid=3887ac09&lang=ar',
            'accept-language': 'ar-IQ,ar;q=0.9',
            'priority': 'u=1, i'
        }

        response = requests.post(url, data=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.text
        else:
            return "عذراً، حدث خطأ في الاتصال بالخادم."
    except Exception as e:
        return f"حدث خطأ: {str(e)}"

# ===========================================================
# دالة إرسال الرسالة إلى فيسبوك
# ===========================================================
def send_facebook_message(recipient_id, text):
    params = {
        "access_token": PAGE_ACCESS_TOKEN
    }
    headers = {
        "Content-Type": "application/json"
    }
    data = {
        "recipient": {"id": recipient_id},
        "message": {"text": text}
    }
    
    r = requests.post("https://graph.facebook.com/v18.0/me/messages", params=params, headers=headers, json=data)
    return r.status_code

# ===========================================================
# نقطة الاتصال (Webhook Route)
# ===========================================================
@app.route('/', methods=['GET', 'POST'])
def webhook():
    # 1. التحقق من الويب هوك (Verification)
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')

        if mode and token:
            if mode == 'subscribe' and token == VERIFY_TOKEN:
                print("WEBHOOK_VERIFIED")
                return challenge, 200
            else:
                return "Verification failed", 403
        return "Hello World", 200

    # 2. استقبال الرسائل (POST)
    if request.method == 'POST':
        data = request.json
        
        # التأكد من أن الطلب قادم من كائن صفحة
        if data.get('object') == 'page':
            for entry in data.get('entry', []):
                for messaging_event in entry.get('messaging', []):
                    
                    sender_id = messaging_event['sender']['id']
                    
                    # --- معالجة الرسائل النصية ---
                    if 'message' in messaging_event and 'text' in messaging_event['message']:
                        user_text = messaging_event['message']['text']
                        
                        # المنطق الخاص بالمطور Aymen Bourai
                        response_text = ""
                        
                        if "aymen bourai" in user_text.lower():
                             response_text = "نعم aymen bourai هو مطوري عمره 18 سنة من مواليد 2007 شخص شاب مبرمج لتطبيقات ومواقع يحب البرمجة واتمنى له مستقبل باهر من ناحية الدراسة لاأعلم عن هذا امر لكنه شخص انطوائي يحب العزلة"
                        elif "من قام بإنتاجك" in user_text or "من مطورك" in user_text:
                             response_text = "aymen bourai هو مطوري وانا مطيع له وأبقى مساعداً له."
                        else:
                            # جلب الرد من API الذكاء الاصطناعي
                            response_text = get_claila_ai_response(user_text)
                        
                        send_facebook_message(sender_id, response_text)

                    # --- معالجة زر "بدء الاستخدام" (Postback) ---
                    elif 'postback' in messaging_event:
                        # عند الضغط على زر البدء، نعتبرها ترحيب ونرد فوراً
                        payload = messaging_event['postback']['payload']
                        if payload == 'GET_STARTED' or True: # الرد على أي زر
                            welcome_text = "أهلاً بك! أنا بوت ذكي تم تطويري بواسطة aymen bourai. اسألني أي سؤال وسأجيبك."
                            send_facebook_message(sender_id, welcome_text)

            return "EVENT_RECEIVED", 200
        else:
            return "Not a page object", 404

# تشغيل التطبيق (للعمل المحلي، ولكن Vercel يديره تلقائياً)
if __name__ == '__main__':
    app.run(debug=True)
