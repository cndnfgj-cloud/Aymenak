import os, json
from datetime import datetime, timedelta, timezone

import requests
from flask import Flask, request, jsonify
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

app = Flask(__name__)

# ====== Config (Vercel env) ======
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "boykta 2023")
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "")
DJZ_CLIENT_ID = os.getenv("DJZ_CLIENT_ID", "6E6CwTkp8H1CyQxraPmcEJPQ7xka")
DJZ_CLIENT_SECRET = os.getenv("DJZ_CLIENT_SECRET", "MVpXHW_ImuMsxKIwrJpoVVMHjRsa")
SESSION_TTL_MIN = int(os.getenv("SESSION_TTL_MIN", "5"))

# Optional DZ proxy per-request (example: http://USER:PASS@IP:PORT)
DZ_PROXY = os.getenv("DZ_PROXY")
PROXIES = {"http": DZ_PROXY, "https": DZ_PROXY} if DZ_PROXY else None

# ====== Robust HTTP session ======
session = requests.Session()
retries = Retry(
    total=3, backoff_factor=0.5,
    status_forcelist=(408, 429, 500, 502, 503, 504),
    allowed_methods=frozenset(["GET","POST"]),
)
adapter = HTTPAdapter(pool_connections=100, pool_maxsize=1000, max_retries=retries)
session.mount("http://", adapter)
session.mount("https://", adapter)

# ====== State (in-memory) ======
processing = set()
sessions = {}

BASE = "https://apim.djezzy.dz"
GRAPH = "https://graph.facebook.com/v17.0/me/messages"

AR_DIGITS = {ord(a): str(i) for i, a in enumerate("٠١٢٣٤٥٦٧٨٩")}
FA_DIGITS = {ord(a): str(i) for i, a in enumerate("۰۱۲۳۴۵۶۷۸۹")}

# ====== Utils ======
def now_utc(): return datetime.now(timezone.utc)
def expire_in(m): return now_utc() + timedelta(minutes=m)

def clean_phone(phone):
    s = "".join(filter(str.isdigit, str(phone or "")))
    if s.startswith("0"): s = s[1:]
    if s.startswith("213"): s = s[3:]
    return s if len(s) == 9 else None

def normalize_digits(s: str) -> str:
    s = (s or "").strip().translate(AR_DIGITS).translate(FA_DIGITS)
    return s.replace(" ", "").replace("-", "")

def _safe_json(r):
    try: return r.json()
    except Exception: return None

def _min_text(r):
    try: return json.dumps(r.json(), ensure_ascii=False).lower()
    except Exception: return (getattr(r, "text", "") or "").lower()

def _contains_payment_problem(text_lc):
    return any(k in text_lc for k in ["payment required","balance is not enough",'"status":402',"402","unauthorized"])

def _is_strict_success(body):
    if not isinstance(body, dict): return False
    status_ok = str(body.get("status","")).strip()=="200"
    code_ok   = str(body.get("code","")).strip()=="200"
    msg_ok = "success" in json.dumps(body, ensure_ascii=False).lower()
    if _contains_payment_problem(json.dumps(body, ensure_ascii=False).lower()): return False
    return status_ok or code_ok or msg_ok

def localize_error(resp, ctx=None):
    f = _min_text(resp)
    pay = _contains_payment_problem(f) or resp.status_code in (402,403)
    if ctx == "70da" and pay: return "❌ رصيدك غير كافي لتفعيل هذا العرض"
    if ctx == "gift" and pay: return "❌ خطأ من شركة جيزي نعتذر"
    if ctx == "1g"  and pay: return "❌ رصيدك غير كافي لتفعيل هذا عرض "
    if resp.status_code == 401: return "❌ غير مصرح: تحقق من صلاحية رمز الدخول."
    if resp.status_code == 404: return "❌ الخدمة غير متاحة مؤقتًا."
    if resp.status_code == 400: return "❌ الطلب غير مكتمل أو غير صالح."
    if resp.status_code == 429: return "❌ محاولات كثيرة. يرجى المحاولة لاحقًا."
    return "❌ حدث خطأ أثناء العملية."

# ====== Djezzy API ======
def d_send_otp(phone):
    msisdn = clean_phone(phone)
    if not msisdn: return False, "❌ رقم الهاتف غير صالح."
    url = f"https://apim.djezzy.dz/oauth2/registration"
    params = {"msisdn": f"213{msisdn}", "scope": "smsotp", "client_id": DJZ_CLIENT_ID}
    payload = {"consent-agreement":[{"marketing-notifications": True}], "is-consent": True}
    headers = {"Content-Type":"application/json","User-Agent":"Djezzy/2.7.3"}
    r = session.post(url, json=payload, params=params, headers=headers, timeout=30, proxies=PROXIES)
    if r.status_code == 200: return True, "✅ تم إرسال رمز التحقق (OTP) إلى رقمك."
    return False, localize_error(r)

def d_verify_otp(phone, otp):
    msisdn = clean_phone(phone)
    if not msisdn: return False, "❌ رقم الهاتف غير صالح.", None
    otp = normalize_digits(otp)
    if not (4 <= len(otp) <= 8) or not otp.isdigit():
        return False, "❌ رمز التحقق غير صالح. اكتب الأرقام فقط بدون مسافات.", None
    url = f"https://apim.djezzy.dz/oauth2/token"
    data = {
        "otp": otp, "mobileNumber": f"213{msisdn}",
        "scope": "openid", "client_id": DJZ_CLIENT_ID,
        "client_secret": DJZ_CLIENT_SECRET, "grant_type": "mobile"
    }
    headers = {
        "user-agent":"Djezzy/2.7.3","connection":"Keep-Alive","accept":"*/*",
        "accept-encoding":"gzip","accept-language":"ar-DZ,ar;q=0.9",
        "host":"apim.djezzy.dz","content-type":"application/x-www-form-urlencoded; charset=utf-8",
    }
    r = session.post(url, data=data, headers=headers, timeout=30, proxies=PROXIES)
    if r.status_code == 200:
        token = r.json().get("access_token")
        if token: return True, "✅ تم التحقق من الرمز بنجاح.", token
    txt = _min_text(r)
    if any(k in txt for k in ["invalid","mismatch","wrong","incorrect"]): return False, "❌ الرمز غير صحيح.", None
    if any(k in txt for k in ["expire","timeout","time out"]): return False, "⌛ انتهت صلاحية الرمز.", None
    if r.status_code == 429: return False, "⛔ محاولات كثيرة. انتظر قليلًا.", None
    if r.status_code == 401: return False, "❌ غير مصرح: اطلب رمزًا جديدًا.", None
    return False, "❌ تعذر التحقق من الرمز.", None

def d_activate_mgm(phone, token, target_phone):
    def _clean(p): 
        s = "".join(filter(str.isdigit, str(p or "")))
        if s.startswith("0"): s = s[1:]
        if s.startswith("213"): s = s[3:]
        return s if len(s) == 9 else None
    a = _clean(phone); b = _clean(target_phone)
    if not a or not b: return False, "❌ أحد أرقام الهاتف غير صالح."
    url = f"https://apim.djezzy.dz/djezzy-api/api/v1/subscribers/213{a}/member-get-member?include="
    payload = {"data":{"id":"MGM-BONUS","type":"products","meta":{"services":{"b-number": f"213{b}","id":"MemberGetMember"}}}}
    headers = {"User-Agent":"Djezzy/2.7.5","Accept-Encoding":"gzip","Authorization": f"Bearer {token}","Content-Type":"application/json; charset=utf-8"}
    r = session.post(url, json=payload, headers=headers, timeout=30, proxies=PROXIES)
    body = _safe_json(r)
    if r.status_code == 200 and _is_strict_success(body): return True, "✅ تمت العملية بنجاح."
    return False, localize_error(r, ctx="mgm")

def d_activate_2go(phone, token):
    msisdn = clean_phone(phone)
    if not msisdn: return False, "❌ رقم الهاتف غير صالح."
    url = f"https://apim.djezzy.dz/djezzy-api/api/v1/subscribers/213{msisdn}/subscription-product?include="
    payload = {"data":{"id":"GIFTWALKWIN","type":"products","meta":{"services":{"steps":10000,"code":"GIFTWALKWIN2GO","id":"WALKWIN"}}}}
    headers = {"User-Agent":"Djezzy/2.7.6","Accept":"application/json","Accept-Encoding":"gzip","Content-Type":"application/json","Authorization": f"Bearer {token}"}
    r = session.post(url, json=payload, headers=headers, timeout=30, proxies=PROXIES)
    body = _safe_json(r)
    if r.status_code == 200 and _is_strict_success(body): return True, "✅ تم تفعيل هدية 2Go بنجاح."
    return False, localize_error(r, ctx="gift")

def d_activate_70da(phone, token):
    msisdn = clean_phone(phone)
    if not msisdn: return False, "❌ رقم الهاتف غير صالح."
    url = f"https://apim.djezzy.dz/djezzy-api/api/v1/subscribers/213{msisdn}/subscription-product?include="
    payload = {"data":{"id":"BTLINTSPEEDDAY2Go","type":"products"}}
    headers = {"User-Agent":"Djezzy/2.7.5","Accept":"*/*","Authorization": f"Bearer {token}","Content-Type":"application/json; charset=utf-8"}
    r = session.post(url, json=payload, headers=headers, timeout=30, proxies=PROXIES)
    body = _safe_json(r)
    if r.status_code == 200 and _is_strict_success(body): return True, "✅ تم تفعيل باقة 70 دج (2Go يومية) بنجاح."
    return False, localize_error(r, ctx="70da") + "\n💡 إن لم يكتمل، جرّب 1G (100 دج) ثم أعد المحاولة."

def d_activate_1g(phone, token):
    msisdn = clean_phone(phone)
    if not msisdn: return False, "❌ رقم الهاتف غير صالح."
    url = f"https://apim.djezzy.dz/djezzy-api/api/v1/subscribers/213{msisdn}/subscription-product?include="
    payload = {"data":{"id":"DOVINTSPEEDDAY1GoPRE","type":"products"}}
    headers = {"User-Agent":"Djezzy/2.7.5","Accept":"*/*","Authorization": f"Bearer {token}","Content-Type":"application/json; charset=utf-8"}
    r = session.post(url, json=payload, headers=headers, timeout=30, proxies=PROXIES)
    body = _safe_json(r)
    if r.status_code == 200 and _is_strict_success(body): return True, "✅ تم تفعيل باقة 1G (100 دج) بنجاح."
    return False, localize_error(r, ctx="1g")

# ====== Messenger send helpers ======
def fb_send(payload):
    params = {"access_token": PAGE_ACCESS_TOKEN}
    headers = {"Content-Type": "application/json"}
    r = requests.post(GRAPH, params=params, headers=headers, json=payload, timeout=20)
    try: _ = r.json()
    except Exception: pass

def send_text(psid, text):
    fb_send({"recipient": {"id": psid}, "messaging_type":"RESPONSE", "message":{"text": text}})

def send_menu_buttons(psid):
    payload = {
        "recipient": {"id": psid},
        "messaging_type": "RESPONSE",
        "message": {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "button",
                    "text": "اختر إجراء للتفعيل السريع:",
                    "buttons": [
                        {"type":"postback","title":"🎁 تفعيل 2Go","payload":"ACTIVATE_2GO"},
                        {"type":"postback","title":"70 دج (2Go)","payload":"ACTIVATE_70DA"},
                        {"type":"postback","title":"1G (100 دج)","payload":"ACTIVATE_1G"}
                    ]
                }
            }
        }
    }
    fb_send(payload)

def send_secondary_buttons(psid):
    payload = {
        "recipient": {"id": psid},
        "messaging_type": "RESPONSE",
        "message": {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "button",
                    "text": "خيارات إضافية:",
                    "buttons": [
                        {"type":"postback","title":"تفعيل الدعوة (MGM)","payload":"ACTIVATE_MGM"},
                        {"type":"postback","title":"🔄 إلغاء العملية","payload":"CANCEL"},
                        {"type":"postback","title":"🏁 ابدأ من جديد","payload":"START"}
                    ]
                }
            }
        }
    }
    fb_send(payload)

# ====== Session helpers ======
def reset_session(psid, say=True):
    sessions.pop(psid, None)
    processing.discard(psid)
    if say:
        send_text(psid, "✅ تم إنهاء العملية.")
        send_menu_buttons(psid)
        send_secondary_buttons(psid)

def lock(psid):
    if psid in processing:
        send_text(psid, "⚠️ توجد عملية قيد التنفيذ. اختر '🔄 إلغاء العملية' أولًا.")
        return False
    processing.add(psid); return True

def step_expired(psid):
    exp = sessions.get(psid, {}).get("expires_at")
    return bool(exp and datetime.now(timezone.utc) > exp)

def start_intro(psid):
    reset_session(psid, say=False)
    send_text(psid, "مرحبًا! اختر خدمة من الأزرار أو أرسل: 2go / 70da / 1g / mgm")
    send_menu_buttons(psid)
    send_secondary_buttons(psid)

# ====== Routing ======
def handle_text(psid, text):
    t = (text or "").strip().lower()
    if t in ("start","/start","menu","/menu"):
        return start_intro(psid)
    if t in ("cancel","/cancel","الغاء","إلغاء"):
        return reset_session(psid, say=True)
    if t in ("2go","70da","1g","mgm"):
        return begin_action(psid, t)
    if psid in sessions:
        return continue_action(psid, t)
    send_text(psid, "أرسل: 2go / 70da / 1g / mgm أو استخدم الأزرار أدناه ⬇️")
    send_menu_buttons(psid)
    send_secondary_buttons(psid)

def handle_postback(psid, payload):
    p = (payload or "").upper()
    if p == "START":
        return start_intro(psid)
    if p == "CANCEL":
        return reset_session(psid, say=True)
    if p == "ACTIVATE_2GO":
        return begin_action(psid, "2go")
    if p == "ACTIVATE_70DA":
        return begin_action(psid, "70da")
    if p == "ACTIVATE_1G":
        return begin_action(psid, "1g")
    if p == "ACTIVATE_MGM":
        return begin_action(psid, "mgm")
    send_text(psid, "لم أفهم الإجراء. استخدم الأزرار.")
    send_menu_buttons(psid)
    send_secondary_buttons(psid)

def begin_action(psid, action):
    if not lock(psid): return
    sessions[psid] = {"action": action, "expires_at": datetime.now(timezone.utc) + timedelta(minutes=SESSION_TTL_MIN)}
    send_text(psid, "📱 أرسل رقم الهاتف (مثال: 0782486704 أو 782486704).")

def continue_action(psid, incoming_text):
    if step_expired(psid):
        reset_session(psid, say=False)
        send_text(psid, "⌛ انتهت الجلسة. اضغط '🏁 ابدأ من جديد'.")
        send_menu_buttons(psid)
        send_secondary_buttons(psid)
        return

    data = sessions.get(psid, {})
    action = data.get("action")

    if "phone" not in data:
        phone = incoming_text
        if not clean_phone(phone):
            send_text(psid, "❌ رقم الهاتف غير صالح. أعد الإرسال.")
            return
        sessions[psid]["phone"] = phone
        ok, msg = d_send_otp(phone)
        send_text(psid, msg)
        if ok:
            sessions[psid]["expires_at"] = datetime.now(timezone.utc) + timedelta(minutes=SESSION_TTL_MIN)
            send_text(psid, "🔢 أرسل رمز التحقق (OTP):")
        else:
            reset_session(psid, say=False)
        return

    if "token" not in data:
        otp = incoming_text
        ok, msg, token = d_verify_otp(data["phone"], otp)
        send_text(psid, msg)
        if ok and token:
            sessions[psid]["token"] = token
            sessions[psid]["expires_at"] = datetime.now(timezone.utc) + timedelta(minutes=SESSION_TTL_MIN)
            if action == "mgm":
                send_text(psid, "📱 أرسل رقم الهاتف المراد دعوته:")
            else:
                if action == "2go":
                    ok2, msg2 = d_activate_2go(data["phone"], token)
                elif action == "70da":
                    ok2, msg2 = d_activate_70da(data["phone"], token)
                elif action == "1g":
                    ok2, msg2 = d_activate_1g(data["phone"], token)
                else:
                    ok2, msg2 = (False, "❌ إجراء غير معروف.")
                send_text(psid, msg2)
                reset_session(psid, say=False)
                send_menu_buttons(psid)
                send_secondary_buttons(psid)
        else:
            reset_session(psid, say=False)
        return

    if action == "mgm" and "token" in data and "phone" in data:
        target = incoming_text
        if not clean_phone(target):
            send_text(psid, "❌ رقم الهاتف المراد دعوته غير صالح. أعد الإرسال.")
            return
        send_text(psid, "⏳ جارٍ تنفيذ الدعوة...")
        ok, msg = d_activate_mgm(data["phone"], data["token"], target)
        send_text(psid, msg)
        reset_session(psid, say=False)
        send_menu_buttons(psid)
        send_secondary_buttons(psid)

# ====== Routes ======
@app.route("/api/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Verification token mismatch", 403

@app.route("/api/webhook", methods=["POST"])
def webhook():
    body = request.get_json(silent=True) or {}
    if body.get("object") != "page":
        return jsonify({"status":"ignored"}), 200

    for entry in body.get("entry", []):
        for event in entry.get("messaging", []):
            psid = event.get("sender", {}).get("id")
            if not psid: 
                continue
            if "postback" in event:
                handle_postback(psid, event["postback"].get("payload"))
                continue
            if "message" in event and "text" in event["message"]:
                handle_text(psid, event["message"]["text"])
            elif "message" in event:
                send_text(psid, "أرسل رسالتك نصيًا فقط.")
                send_menu_buttons(psid)
                send_secondary_buttons(psid)
    return jsonify({"status":"ok"}), 200

@app.route("/api/healthz")
def health():
    return jsonify({"ok": True, "time": datetime.utcnow().isoformat()})
