# ELGALAD — Bilingual Arabic/English AI Summarizer (Django)

موقع Django احترافي بلوحة تحكم كاملة، مربوط بموديل التلخيص ثنائي اللغة (FastAPI) عن طريق الـ endpoint.

## التشغيل (Windows)

1. ثبّت **Python 3.10 أو أحدث** (وعلّم على *Add Python to PATH*).
2. دبل كليك على **`run.bat`** — أول مرة هيعمل venv ويثبت المكتبات ويجهز قاعدة البيانات لوحده، وبعدين يفتح الموقع على `http://127.0.0.1:8000`.
3. **أول حساب تعمله من صفحة "إنشاء حساب" بيبقى هو الأدمن** (يشوف كل المستخدمين، ويغيّر رابط الموديل، ويدخل `/admin/`).

(`setup.bat` موجود كمان لو عايز تعمل التثبيت لوحده من غير ما تشغل السيرفر.)

تشغيل يدوي (أي نظام):

```bash
python -m venv .venv
.venv\Scripts\activate          # Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
python manage.py makemigrations core
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## ربط الموديل

- الرابط الافتراضي موجود في ملف `.env` → `AI_API_BASE_URL`.
- روابط **trycloudflare بتتغير كل مرة تشغّل فيها الـ tunnel**، فتقدر تغيّر الرابط من جوه الموقع:
  **الإعدادات ← نموذج الذكاء الاصطناعي** (للأدمن بس) — من غير ما تلمس الكود.
- كل الـ endpoints اللي في الـ Postman collection مربوطة:

| Endpoint | مستخدم في |
|---|---|
| `GET /` , `GET /health` | مؤشر حالة الموديل + صفحة المراقبة |
| `POST /api/v1/summarize` | صفحة **تلخيص نص** |
| `POST /api/v1/summarize/batch` | صفحة **تلخيص مجمّع** (حتى 32 مستند) |
| `POST /api/v1/detect-language` | **أدوات NLP** ← اكتشاف اللغة |
| `POST /api/v1/clean-text` | **أدوات NLP** ← تنظيف النص |
| `POST /api/v1/tokenize` | **أدوات NLP** ← التقطيع والإحصائيات |

## المميزات

- صفحة رئيسية (Landing) احترافية + تسجيل دخول / إنشاء حساب.
- واجهة **عربي / إنجليزي** بزرار تبديل (RTL/LTR) + **وضع ليلي**.
- **لوحة تحكم**: KPIs، رسوم بيانية (النشاط اليومي، توزيع اللغات، زمن الاستجابة، نسبة الاختصار)، آخر الملخصات، حالة الموديل لايف.
- **تلخيص نص**: لصق نص أو رفع ملف (TXT / DOCX / PDF)، التحكم في كل إعدادات التوليد (max/min length, beams, penalties…) + قوالب جاهزة.
- **تلخيص مجمّع** مع تصدير CSV.
- **أدوات NLP**: اكتشاف اللغة، تنظيف النص، التقطيع والإحصائيات.
- **السجل**: بحث، فلترة باللغة/النوع، مفضلة، تحميل، حذف، تصدير CSV.
- **مراقبة الموديل**: كل طلب بيتسجل (الحالة، الزمن، الأخطاء) + إحصائيات لكل endpoint.
- **إدارة المستخدمين** للأدمن + لوحة Django Admin على `/admin/`.

## هيكل المشروع

```
config/            إعدادات Django
core/
  api_client.py    الكلاينت اللي بيكلم الموديل (كل الـ endpoints)
  models.py        Summary · ApiCallLog · AIConfig
  views.py         الصفحات + JSON endpoints الداخلية
  i18n.py          قاموس الترجمة عربي/إنجليزي
  file_extract.py  استخراج النص من PDF/DOCX/TXT
templates/         القوالب (public · auth · app)
static/            CSS + JS (Chart.js للرسوم)
```
