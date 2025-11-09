import os, requests
from flask import Flask, request, jsonify

app = Flask(__name__)
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "")

def call_profile(payload):
    url = f"https://graph.facebook.com/v17.0/me/messenger_profile?access_token={PAGE_ACCESS_TOKEN}"
    r = requests.post(url, json=payload, timeout=30)
    try: return r.json()
    except Exception: return {"status": r.status_code, "text": r.text}

@app.route("/api/setup/profile", methods=["POST"])
def setup_profile():
    payload = {
        "greeting": [{"locale":"default","text":"مرحبًا بك في مساعد جيزي الذكي! اختر من الأزرار أو اكتب 2go / 70da / 1g / mgm"}],
        "get_started": {"payload":"START"},
        "persistent_menu": [{
            "locale":"default",
            "composer_input_disabled": False,
            "call_to_actions":[
                {"type":"postback","title":"🎁 تفعيل 2Go","payload":"ACTIVATE_2GO"},
                {"type":"postback","title":"70 دج (2Go)","payload":"ACTIVATE_70DA"},
                {"type":"postback","title":"1G (100 دج)","payload":"ACTIVATE_1G"},
                {"type":"postback","title":"تفعيل الدعوة (MGM)","payload":"ACTIVATE_MGM"},
                {"type":"postback","title":"🏁 ابدأ من جديد","payload":"START"}
            ]
        }],
        "ice_breakers":[
            {"question":"أريد تفعيل 2Go","payload":"ACTIVATE_2GO"},
            {"question":"أريد تفعيل 70 دج (2Go)","payload":"ACTIVATE_70DA"},
            {"question":"أريد تفعيل 1G (100 دج)","payload":"ACTIVATE_1G"},
            {"question":"تفعيل الدعوة (MGM)","payload":"ACTIVATE_MGM"}
        ]
    }
    return jsonify(call_profile(payload))

@app.route("/api/setup/delete", methods=["POST"])
def delete_fields():
    fields = request.json.get("fields", ["greeting","get_started","persistent_menu","ice_breakers"])
    url = f"https://graph.facebook.com/v17.0/me/messenger_profile?access_token={PAGE_ACCESS_TOKEN}"
    r = requests.delete(url, json={"fields": fields}, timeout=30)
    try: return jsonify(r.json())
    except Exception: return jsonify({"status": r.status_code, "text": r.text})

@app.route("/api/healthz")
def health():
    return jsonify({"ok": True})
