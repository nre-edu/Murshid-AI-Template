# دليل (Daleel) — قالب عام

قالب عام مستقل لمساعد دردشة عربي يبحث في ملفات Markdown داخل مجلد `Knowledge/` ويجيب **من المصادر المعتمدة فقط**، مع استشهادات رقمية ومقتطفات، وخريطة إجابة اختيارية للأسئلة الهيكلية.

> هذه الحزمة تحتوي **عيّنة DEMO فقط** عن أساسيات الذكاء الاصطناعي.  
> **لا تضع أدلتك المؤسسية أو الخاصة في مستودع عام.**

## ملاحظة مهمة عن المزامنة

هذا القالب العام والنسخة الخاصة الأصلية (`Daleel-Free-Web`) **لا يتزامنان تلقائيًا**.  
أي تحسينات أو إصلاحات في الأصل يجب **نقلها يدويًا** إلى هذا القالب عند الرغبة في نشرها للعامة.

## الترخيص

المرخّص بموجب **MIT** — انظر ملف [`LICENSE`](LICENSE).  
يمكنك استخدام القالب ونسخه وتعديله ونشر نسخك الخاصة بحرية وفق شروط MIT.

## المميزات

- استرجاع مقاطع من ملفات Markdown داخل `Knowledge/` (مع استثناء `Knowledge/_examples/`).
- إجابات عبر Gemini استنادًا للمقاطع المسترجعة فقط؛ عند غياب الدليل يُصرَّح بعدم الكفاية.
- استشهادات قابلة للعرض من الخادم (المحتوى لا يُخدم عبر `/static`).
- فهرسة وقت البناء مناسبة لنشر Vercel (نظام ملفات للقراءة فقط).

## المتطلبات

- Python 3.10+
- مفتاح [Google Gemini API](https://aistudio.google.com/apikey) خاص بك (طبقة مجانية حسب مشروعك في AI Studio)

## التشغيل المحلي

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

يوجد أيضًا `requirements.lock` لتثبيت إصدارات مجمّدة عند الحاجة: `pip install -r requirements.lock`.

1. انسخ بيئة المثال:
   ```bash
   cp .env.example .env
   ```
2. ضع مفتاحك في `.env` (لا ترفع `.env` أبدًا):
   ```env
   GEMINI_API_KEY=
   GEMINI_MODEL=gemini-3.5-flash-lite
   ```
3. ابنِ فهرس المعرفة:
   ```bash
   python scripts/build_knowledge_index.py
   ```
4. شغّل الخادم:
   ```bash
   python run.py
   ```
5. افتح: http://127.0.0.1:8000

زر **«إضافة مفتاح الذكاء»** يعرض تعليمات الإعداد فقط؛ لا يحفظ المفتاح من الواجهة ولا يعرض قيمته.

راجع أيضًا ملف [`DEMO.md`](DEMO.md) و[`docs/DEMO_TEST_QUESTIONS.md`](docs/DEMO_TEST_QUESTIONS.md).

## ملف `.env.example`

انسخه إلى `.env` واملأ القيم محليًا فقط. المتغيرات الأساسية:

| المتغير | الوصف |
|--------|--------|
| `GEMINI_API_KEY` | مفتاح الخادم (فارغ في المثال عمدًا) |
| `GEMINI_MODEL` | الافتراضي: `gemini-3.5-flash-lite` |
| `MAX_QUERY_CHARS` | حد طول السؤال (اختياري) |
| `RATE_LIMIT_PER_MINUTE` | حد تقريبي لكل نسخة عملية (اختياري) |

على Vercel: أضف المتغيرات من Project → Settings → Environment Variables كمتغيرات **خادم فقط** (بلا `NEXT_PUBLIC_` / `VITE_`).

## مجلد Knowledge

| المسار | الدور |
|--------|--------|
| `Knowledge/*.md` | أدلة Markdown مفهرسة |
| `Knowledge/_examples/` | أسئلة/عيّنات **مستبعدة من الفهرسة** |
| `docs/DEMO_TEST_QUESTIONS.md` | أسئلة تجربة خارج فهرس الإجابة |

الملفات المدعومة: `.md` / `.markdown` بترميز UTF-8. يُفضّل واجهة YAML أعلى الملف (`id`, `title`, …).

**حالة الأحرف:** استخدم الاسم `Knowledge` (حساس على Linux/Vercel).

### استبدال العيّنة ثم إعادة البناء / إعادة النشر

1. احذف ملف(ات) DEMO من `Knowledge/`.
2. ضع ملفاتك `.md` (في نسخة خاصة أو محلية — ليس في المستودع العام إن كانت سرية).
3. نفّذ: `python scripts/build_knowledge_index.py`
4. محليًا: أعد تشغيل الخادم. على Vercel: ادفع التغييرات أو أعد النشر (Redeploy).

> على بيئة النشر لا تُكتب الأسرار أو الفهرس وقت التشغيل. أي إضافة/تعديل/حذف للأدلة يستلزم **إعادة البناء وإعادة النشر**.

## أسئلة التجربة

أمثلة من [`docs/DEMO_TEST_QUESTIONS.md`](docs/DEMO_TEST_QUESTIONS.md):

- داخل المصدر: «ما الذكاء الاصطناعي؟ اذكر تطبيقين وردا في الدليل.»
- خارج المصدر: «كم سعر اشتراك ChatGPT اليوم؟» → يجب الامتناع لعدم كفاية المصادر.

## الخصوصية والمستودع العام

- المستودع العام يكشف كل ما يُرفع إليه. **لا تضف أدلتك الخاصة إلى مستودع عام.**
- استخدم نسخة محلية أو مستودعًا خاصًا لأدلتك، وانشر على Vercel من ذلك المسار إن لزم.
- لا ترفع `.env` أو مفاتيح API.
- محتوى `Knowledge/` والفهرس للخادم فقط؛ لا يُضمَّن كاملًا في حزمة JavaScript للمتصفح.

## النشر على Vercel

1. من GitHub: استخدم **Use this template** لإنشاء مستودع جديد، أو Import المشروع في Vercel.
2. Framework: يُكتشف FastAPI عادةً تلقائيًا (`app` في `app/main.py`).
3. Build Command (موجود في `vercel.json`): `python scripts/build_knowledge_index.py`
4. Install: `pip install -r requirements.txt`
5. Environment Variables (Production/Preview):
   - `GEMINI_API_KEY` = مفتاحك (Server)
   - اختياري: `GEMINI_MODEL=gemini-3.5-flash-lite`
6. Deploy ثم اختبر الموقع.
7. بعد تغيير ملفات `Knowledge/`: ابنِ الفهرس وادفع ثم Redeploy.

## حدود الخطط المجانية (تقديرية — راجع الوثائق الرسمية)

- **Vercel Hobby:** استخدام شخصي غير تجاري؛ حدود CPU/ذاكرة/استدعاءات شهرية؛ مدة دالة محدودة. راجع [Vercel Hobby](https://vercel.com/docs/plans/hobby).
- **Gemini API Free:** حصص حسب المشروع في AI Studio؛ قد تتغير. نفاد الحصة يظهر برسالة مفهومة دون كشف المفتاح.
- النشر على الخطة المجانية **لا يضمن تكلفة صفر مستقبلًا** إذا فعّلت الفوترة أو تجاوزت شروط الخدمات.

حد المعدل داخل التطبيق (`RATE_LIMIT_PER_MINUTE`) يعمل **داخل نسخة العملية فقط**؛ على Vercel متعدد النسخ ليس حماية شاملة.

## المشكلات الشائعة

| العرض | الحل |
|--------|------|
| «الإعداد غير مكتمل» | أضف `GEMINI_API_KEY` في `.env` أو Vercel Env ثم أعد التشغيل/النشر |
| لا مصادر / فهرس فارغ | تأكد من ملفات `.md` في `Knowledge/` ثم `python scripts/build_knowledge_index.py` |
| إجابات عن مواضيع خارج الدليل | متوقع الامتناع؛ تحقق أن أسئلة الاختبار ليست داخل ملفات مفهرسة |
| 429 / نفاد الحصة | انتظر أو راجع حدود AI Studio |
| اختلاف المسار على Linux | استخدم `Knowledge` بحرف K كبير |

## هيكل مختصر

```
Knowledge/                 # أدلة Markdown (خادم فقط)
Knowledge/_examples/       # أسئلة تجربة — غير مفهرسة
docs/                      # وثائق وأسئلة DEMO
app/                       # FastAPI + الاسترجاع + Gemini
static/                    # الواجهة فقط
scripts/build_knowledge_index.py
data/knowledge_index.json  # ناتج البناء (يُنشأ محليًا / وقت Build)
LICENSE                    # MIT
.env.example               # أسرار فارغة للنسخ المحلي
```
