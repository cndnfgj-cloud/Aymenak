# Aymen Facebook Messenger Bot (Vercel + Python)

هذا مشروع بسيط لبوت فيسبوك ماسنجر يعمل على Vercel باستخدام Python runtime.

- نقطة الدخول: `api/webhook.py`
- البوت يرد فقط نصياً (بدون أزرار ولا اتخاذ إجراء).
- يستعمل API خارجية: `https://vetrex.x10.mx/api/gpt4.php?text=YOUR_TEXT`

## هيكلة الملفات

يجب أن تبدو ملفات الريبو في GitHub هكذا:

```text
.
├── api
│   └── webhook.py
├── requirements.txt
└── README.md
```

لا يوجد أي ملف `vercel.json` هنا، حتى لا تحدث مشاكل الرن تايم القديمة (now-php وغيرها).

ارفع هذا الريبو لــ GitHub، ثم اربطه مع Vercel، وأضف متغيرات البيئة:

- `PAGE_ACCESS_TOKEN`
- `VERIFY_TOKEN`

ثم فعّل الـ Webhook في Facebook Developers بالرابط:

`https://YOUR-PROJECT-NAME.vercel.app/api/webhook`
