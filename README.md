# Facebook Messenger Djezzy Bot — Buttons Edition (Vercel + Python)

**المزايا:**
- أزرار واضحة لتفعيل: 2Go / 70 دج (2Go) / 1G (100 دج) / MGM
- تدفّق بسيط: رقم الهاتف → OTP → تفعيل (مع مهلة قابلة للتعديل)
- بروكسي جزائري *per-request* عبر `DZ_PROXY`
- مسارات إعداد للصفحة (Greeting / Get Started / Persistent Menu / Ice Breakers)

## الإعداد على Vercel (لدومينك: aymenak.vercel.app)
Environment Variables:
- `PAGE_ACCESS_TOKEN`  (من Meta)
- `VERIFY_TOKEN`       = `boykta 2023`
- `DJZ_CLIENT_ID`      = (قيمة صحيحة)
- `DJZ_CLIENT_SECRET`  = (قيمة صحيحة)
- (اختياري) `DZ_PROXY` = `http://USER:PASS@IP:PORT`
- (اختياري) `SESSION_TTL_MIN` = 5

> لديك بروكسيك:
> `http://1txdywkvli-corp.mobile.res-country-DZ-state-2507475-city-2507480-hold-session-session-68d4220296c61:QwrncPtM2rex7t39@89.38.99.242:9999`
> ضعه في متغير `DZ_PROXY` (لا تضعه داخل الكود).

## ربط فيسبوك
- Callback URL: `https://aymenak.vercel.app/api/webhook`
- Verify Token: `boykta 2023`
- Events: `messages, messaging_postbacks`

## تفعيل واجهة الصفحة (مرة واحدة)
```bash
curl -X POST https://aymenak.vercel.app/api/setup/profile
```

## الاستخدام
- أول دخول: سيظهر Greeting و Ice Breakers و Get Started (أوتوماتيكي).
- اضغط زر **🎁 تفعيل 2Go** أو أرسل: `2go`
- التدفّق: رقم الهاتف → OTP → تنفيذ التفعيل → رسالة النتيجة + ظهور الأزرار مرة أخرى.
- نفس الشيء لـ `70da`، `1g`، و `mgm` (الأخير يطلب رقمًا ثانيًا للدعوة).

## ملاحظات
- الحالة (الجلسات) في الذاكرة—قد تفقد عند إعادة النشر (طبيعي مع serverless).
- التزم بسياسات Djezzy و Meta.
- لا تضع أي أسرار داخل الكود العام.
