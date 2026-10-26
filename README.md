# مساعد B12 لولي الأمر

بيفوت على تطبيق المدرسة B12 بحساب الطالب (Microsoft)، وبيقرأ الرسائل والـ Weekly plan والـ Newsletter والتذكيرات، وبيطلع منها المهام مرتبة حسب التاريخ: واجبات، أغراض لازم تنجاب، امتحانات، وواجبات على Teams أو Kutobee أو Tamreen. بعدين بتسألي من صفحة ويب «شو عنا بكرا؟» وبيجاوبك عن بكرا، وبيذكرك بالي بعده.

## كيف بيشتغل

1. **السحب** (`b12/scraper.py`): B12 ما عنده API، فالسكربت بيفتح متصفح (Playwright) وبيعمل تسجيل الدخول بـ Microsoft، وبعدين بيقرأ الصفحات المحددة في `selectors.json` وبينزّل ملفات الـ PDF.
2. **التخزين** (`b12/store.py`): قاعدة SQLite على جهازك (`data/b12.sqlite`) فيها الرسائل والمهام.
3. **الاستخراج** (`b12/llm.py`): Claude بيقرأ كل رسالة جديدة (والـ PDF المرفق إذا في)، وبيحول التواريخ النسبية متل «بكرا» أو «الأحد الجاي» لتاريخ محدد، وبيرجع قائمة مهام منظمة.
4. **الإجابة**: لما تسألي، بنجيب مهام الأسبوعين الجايين من القاعدة وبنعطيها لـ Claude، وهو بيجاوب بالعربي ومرتب حسب اليوم. ما بنستعمل بحث vector لأن الأسئلة كلها عن تواريخ، فالبحث حسب التاريخ أدق.
5. **الواجهة** (`b12/web.py`): صفحة ويب على `http://localhost:8000`. بوت واتساب (`b12/whatsapp.py`) جاهز، وبيشتغل لما تعبي إعدادات Meta.

## التنصيب على Windows

```powershell
cd C:\path\to\b12-assistant
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
copy .env.example .env
notepad .env
```

بملف `.env` عبي `ANTHROPIC_API_KEY` (من console.anthropic.com). ملف `.env` ما بينرفع على GitHub.

## الاستعمال

```powershell
python -m b12 serve
```

افتحي http://localhost:8000. أول مرة بتطلب الصفحة إيميل الطالب وكلمة السر، وبتعمل تسجيل الدخول على B12 بالخلفية. كلمة السر بتنحفظ بمخزن كلمات السر بالجهاز (Windows Credential Manager)، مش بملف. ومن زر «تسجيل خروج» بتنمسح.

أوامر إضافية للضبط والتجربة:

```powershell
python -m b12 login      # بيفتح متصفح ظاهر، مفيد إذا B12 طلب خطوة إضافية بالدخول
python -m b12 discover   # بيحفظ صور وصفحات B12 في data\discover لنضبط selectors.json
python -m b12 sync       # بيسحب الرسائل الجديدة وبيستخرج المهام
python -m b12 ask "شو عنا بكرا؟"
```

## ضبط صفحات B12 (`selectors.json`)

كل عنصر في `sections` هو صفحة من B12:

| الحقل | المعنى |
|---|---|
| `name` | اسم المصدر، مثلاً `b12-weekly-plan` |
| `url` | رابط الصفحة، أو مسارها نسبةً لـ `B12_URL` |
| `item_selector` | CSS لكل رسالة بالقائمة. إذا ما حطيتيه، بنقرأ نص الصفحة كلها كرسالة وحدة |
| `title_selector`, `date_selector`, `body_selector` | أجزاء داخل كل رسالة |
| `open_item` | `true` لنفتح كل رسالة ونقرأ تفاصيلها، مع `detail_selector` و`attachment_selector` |
| `max_items` | أقصى عدد رسائل نقرأه بكل مرة (الافتراضي 20) |

بعد ما تشغلي `discover`، الصفحات اللي انحفظت بـ `data\discover` بتساعدنا نعبي هالملف.

## واتساب (لاحقاً)

عبي `WHATSAPP_*` و`ALLOWED_WHATSAPP_NUMBER` بملف `.env`، واعملي رابط عام للجهاز (مثلاً `ngrok http 8000`)، وحطي `https://<الرابط>/webhook` بإعدادات WhatsApp في Meta مع نفس `WHATSAPP_VERIFY_TOKEN`. البوت بيرد بس على الرقم المسموح، وبيبعت ملخص كل يوم الصبح الساعة `MORNING_REMINDER_HOUR`.
