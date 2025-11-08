# Facebook Messenger Bot (Vercel + Python + Flask)

جاهز للنشر على Vercel. هذا المشروع يحول منطقك السابق إلى Webhook لفيسبوك ماسنجر
مع أزرار و Quick Replies، ويعتمد على واجهة Vulcan للردود الذكية.

## الملفات

- `api/index.py` : تطبيق Flask مع مسارين:
  - `GET /api/webhook` للتحقق من التوكن (VERIFY_TOKEN)
  - `POST /api/webhook` لاستقبال رسائل المستخدمين والرد عليهم مباشرةً
- `requirements.txt` : المكتبات المطلوبة
- `vercel.json` : (اختياري) لتثبيت المسارات

> تم ضبط VERIFY_TOKEN افتراضياً على: `boykta 2023` كما طلبت.

## المتغيرات (Environment Variables) على Vercel

أضف في إعدادات المشروع على Vercel:

- `PAGE_ACCESS_TOKEN` : توكن صفحة فيسبوك من Meta
- `VERIFY_TOKEN` : يمكن تركها `boykta 2023` أو تغييره لاحقاً
- `DEVICE_ID` : نفس المعرف المستخدم مع Vulcan (إن رغبت بتغييره)
- (اختياري) `MAX_CHAT_HISTORY` و `MAX_TOKENS`

## النشر

1. ارفع هذا المشروع إلى GitHub.
2. وصّل المستودع مع Vercel.
3. عند النشر، سيصبح عنوان الويب هو:
   `https://<your-project>.vercel.app/api/webhook`

استخدم هذا العنوان لإعداد Webhook في تطبيق Meta.

## تفعيل الـ Webhook على Meta

- في لوحة تطبيقك على developers.facebook.com:
  - Products → Messenger → Settings
  - Webhooks → Add Callback URL
  - ضع:
    - Callback URL: `https://<your-project>.vercel.app/api/webhook`
    - Verify Token: `boykta 2023` (أو ما وضعته في env)
  - اشترك في الحقول (messages, messaging_postbacks) لصفحتك.

### تجاوز "زر بدء الاستخدام"
فيسبوك يشترط أن يبدأ المستخدم المحادثة أولاً (بالضغط على "Start" أو بإرسال رسالة).
هذا الكود يرد **فوراً** على أي رسالة تصل (لا حاجة لأوامر خاصة مثل /start).
لتفعيل زر "بدء الاستخدام" مرّة واحدة:
```bash
curl -X POST "https://graph.facebook.com/v17.0/me/messenger_profile?access_token=$PAGE_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"get_started":{"payload":"GET_STARTED"}}'
```
وسيتم التعامل مع الـ payload داخل الكود.

## الأزرار و Quick Replies
- يرسل البوت Quick Replies عربية بعد كل رد.
- يرسل أيضاً رسالة "زرّية" (Button Template) باختيارات مثل "مساعدة" و"ابدأ محادثة جديدة" ورابط موقع.

لتعديل الأزرار:
- حرّر دوال `default_quick_replies` و `default_buttons` في `api/index.py`.

## ملاحظات
- التخزين هنا في الذاكرة (in-memory). على بيئة serverless قد تُفقد الذاكرة بعد الـ cold start.
- احرص على إبقاء توكن الصفحة سرياً في متغيرات البيئة.
- إذا رغبت بحفظ محادثات بشكل دائم، استخدم قاعدة بيانات خارجية (مثل Upstash Redis أو PlanetScale).

بالتوفيق ✨
