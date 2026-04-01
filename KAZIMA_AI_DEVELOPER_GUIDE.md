# كاظمة AI — دليل المبرمج الكامل

## ما هو هذا المشروع

كاظمة AI هو نظام مساعد بحثي متخصص في التاريخ الديني الخليجي وتحقيق المخطوطات.
مبني داخل مشروع Next.js 14 قائم (سكة كار) ويستخدم نفس البنية التحتية.

---

## المتطلبات

| المكون | الإصدار | الملاحظات |
|--------|---------|-----------|
| Node.js | 18+ | مطلوب |
| PostgreSQL | 14+ | عبر Supabase أو محلي |
| Prisma | 5.22+ | موجود في المشروع |
| Next.js | 14.2.18 | موجود في المشروع |
| مفتاح API | Anthropic أو OpenAI | واحد على الأقل مطلوب |

---

## الخطوة 1: إعداد البيئة

### 1.1 استنساخ المشروع والانتقال للفرع

```bash
git clone https://github.com/alshatreee/sikka-car.git
cd sikka-car
git checkout claude/review-system-prompts-rPG6B
npm install
```

### 1.2 إعداد متغيرات البيئة

انسخ ملف البيئة:

```bash
cp .env.example .env
```

افتح `.env` واملأ المتغيرات التالية:

```env
# قاعدة البيانات — Supabase PostgreSQL
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@db.YOUR_PROJECT.supabase.co:5432/postgres
DIRECT_URL=postgresql://postgres:YOUR_PASSWORD@db.YOUR_PROJECT.supabase.co:5432/postgres

# كاظمة AI — اختر مزود واحد
# الخيار أ: Anthropic (يأخذ الأولوية إذا وُجد)
ANTHROPIC_API_KEY=sk-ant-api03-...

# الخيار ب: OpenAI أو متوافق مع OpenAI
# OPENAI_API_KEY=sk-...
# OPENAI_BASE_URL=https://api.openai.com/v1

# اختياري: تغيير النموذج الافتراضي
# KAZIMA_MODEL_ID=claude-sonnet-4-20250514
```

**تنبيه:** إذا وضعت `ANTHROPIC_API_KEY` و `OPENAI_API_KEY` معًا، النظام يستخدم Anthropic.

### 1.3 تهيئة قاعدة البيانات

```bash
npx prisma generate
npx prisma db push
```

هذا ينشئ 4 جداول جديدة في قاعدة البيانات:
- `KazimaAnalysis` — نتائج التحليلات المحفوظة
- `KazimaManuscript` — المخطوطات
- `KazimaDocument` — قاعدة المعرفة (النصوص المرجعية)
- `KazimaGraphData` — بيانات شبكة العلاقات

### 1.4 تشغيل المشروع

```bash
npm run dev
```

افتح المتصفح: `http://localhost:3000/kazima`

---

## الخطوة 2: فهم بنية الملفات

```
sikka-car/
├── lib/
│   ├── kazima-ai.ts          # هوية كاظمة: system prompt + 9 أوضاع + validation
│   ├── kazima-llm.ts         # استدعاء LLM (Anthropic + OpenAI) + JSON parsing
│   ├── kazima-prompts.ts     # برومبتات الاستخراج البنيوي (JSON output)
│   └── kazima-cleaner.ts     # تنظيف النص العربي
│
├── app/
│   ├── api/kazima-ai/
│   │   ├── route.ts              # POST /api/kazima-ai — تحليل بسيط
│   │   ├── analyze-full/route.ts # POST /api/kazima-ai/analyze-full — تحليل شامل
│   │   └── chat/route.ts         # POST /api/kazima-ai/chat — محادثة RAG
│   │
│   └── kazima/
│       ├── page.tsx          # الصفحة الرئيسية (Hub)
│       ├── analyze/page.tsx  # صفحة التحليل الشامل
│       └── chat/page.tsx     # صفحة المحادثة
│
├── components/kazima/
│   ├── KazimaInput.tsx       # مكون الإدخال (اختيار الوضع + النص)
│   ├── KazimaResult.tsx      # عرض النتائج (نسخ + تحميل + حفظ)
│   └── KazimaHistory.tsx     # سجل التحليلات المحفوظة
│
├── actions/
│   └── kazimaActions.ts      # Server Actions (حفظ/استرجاع/حذف)
│
└── prisma/
    └── schema.prisma         # 4 جداول كاظمة (من سطر 207)
```

**إجمالي الكود:** 2,617 سطر موزعة على 14 ملف.

---

## الخطوة 3: فهم الـ API Endpoints

### 3.1 التحليل البسيط — `POST /api/kazima-ai`

يرسل النص إلى LLM مع أحد الأوضاع التسعة ويعيد النتيجة كنص.

**الطلب:**
```json
{
  "mode": "analysis",
  "text": "النص المراد تحليله",
  "additionalContext": "سياق إضافي (اختياري)"
}
```

**الأوضاع المتاحة (9):**

| الوضع | الوصف | نوع المخرج |
|-------|-------|-----------|
| `analysis` | تحليل نصي نقدي (كشف التصحيف والسقط) | نص حر |
| `extraction` | استخراج أعلام وأماكن وتواريخ | نص حر (ليس JSON) |
| `annotation` | كتابة حواشٍ علمية | نص حر |
| `publication` | صياغة أكاديمية للنشر | نص حر |
| `media` | تحويل لسلايدات سوشيال ميديا | نص حر |
| `review` | مراجعة ذاتية نقدية | نص حر |
| `comparison` | مقارنة بين تفسيرين | نص حر |
| `error-detection` | كشف الأخطاء والتناقضات | نص حر |
| `manuscript-expert` | تحليل كمخطوطة (الفترة والمدرسة) | نص حر |

**الاستجابة:**
```json
{
  "mode": "analysis",
  "result": "نتيجة التحليل...",
  "timestamp": "2026-04-01T12:00:00.000Z"
}
```

**حدود:**
- الحد الأقصى للنص: 50,000 حرف
- يجب أن يكون النص غير فارغ

---

### 3.2 التحليل الشامل — `POST /api/kazima-ai/analyze-full`

يشغّل 4 عمليات استخراج **متوازية** ويعيد بيانات منظمة (JSON).

**الطلب:**
```json
{
  "text": "تولى عبدالله بن صباح الحكم في الكويت سنة 1762 وانتقل إلى الزبير"
}
```

**الاستجابة:**
```json
{
  "entities": {
    "persons": ["عبدالله بن صباح"],
    "locations": ["الكويت", "الزبير"],
    "books": [],
    "tribes": [],
    "dates": ["1762"],
    "keywords": ["الحكم", "الانتقال"],
    "text_type": "تاريخ سياسي",
    "confidence_level": "high"
  },
  "relations": {
    "relations": [
      { "from": "عبدالله بن صباح", "to": "الكويت", "type": "حكم", "uncertain": false },
      { "from": "عبدالله بن صباح", "to": "الزبير", "type": "انتقال", "uncertain": false }
    ]
  },
  "timeline": {
    "timeline": [
      { "event": "تولي الحكم", "year": "1762", "calendar": "gregorian", "approximate": false }
    ]
  },
  "classification": {
    "classification": {
      "primary": "تاريخ سياسي",
      "secondary": ["تراجم وطبقات"],
      "region": "الكويت",
      "period": "القرن 18",
      "importance": "high"
    }
  },
  "graph": {
    "nodes": [
      { "id": "عبدالله بن صباح", "type": "person", "label": "عبدالله بن صباح" },
      { "id": "الكويت", "type": "location", "label": "الكويت" },
      { "id": "الزبير", "type": "location", "label": "الزبير" }
    ],
    "edges": [
      { "source": "عبدالله بن صباح", "target": "الكويت", "type": "حكم" },
      { "source": "عبدالله بن صباح", "target": "الزبير", "type": "انتقال" }
    ]
  },
  "timestamp": "2026-04-01T12:00:00.000Z"
}
```

**ملاحظة مهمة:** العمليات الأربع تعمل بالتوازي (`Promise.all`). هذا يعني أن الطلب يستغرق وقت أطول عملية واحدة، لا مجموعها.

---

### 3.3 المحادثة — `POST /api/kazima-ai/chat`

محادثة RAG: يبحث في قاعدة المعرفة ثم يجيب بناءً على السياق.

**الطلب:**
```json
{
  "query": "من حكم الكويت في القرن 18؟",
  "conversationHistory": [
    { "role": "user", "content": "سؤال سابق" },
    { "role": "assistant", "content": "إجابة سابقة" }
  ]
}
```

**الاستجابة:**
```json
{
  "answer": "بحسب المصادر المتوفرة في قاعدة كاظمة...",
  "sources": [
    { "title": "تاريخ الكويت", "source": "كتاب تاريخ الكويت" }
  ],
  "hasContext": true,
  "timestamp": "2026-04-01T12:00:00.000Z"
}
```

**كيف يعمل البحث:**
1. يُنظَّف السؤال (إزالة تشكيل + توحيد حروف)
2. يُقسَّم لمصطلحات بحث (حد أدنى حرفين، حد أقصى 10 مصطلحات)
3. يبحث في جدول `KazimaDocument` (حد أقصى 5 نتائج)
4. يبحث في جدول `KazimaAnalysis` (حد أقصى 3 نتائج)
5. يبني السياق ويرسله للنموذج مع السؤال

**تنبيه:** البحث حاليًا **لفظي** (يبحث عن الكلمة نفسها). لا يوجد بحث دلالي (embeddings) بعد.

---

## الخطوة 4: تعبئة قاعدة المعرفة

قاعدة المعرفة فارغة في البداية. المحادثة لن تعمل بكفاءة بدون بيانات.

### الطريقة: استخدام Server Actions

في أي ملف Server Component أو Server Action، استدعِ:

```typescript
import { addKazimaDocument } from '@/actions/kazimaActions'

await addKazimaDocument({
  title: 'تاريخ حكام الكويت',
  content: 'النص الكامل هنا...',
  source: 'كتاب تاريخ الكويت - المؤلف',
  author: 'اسم المؤلف',
  period: 'القرن 18-19',
  region: 'الكويت',
  category: 'تاريخ سياسي',
  tags: ['الكويت', 'آل صباح', 'تاريخ سياسي'],
})
```

**تنبيه:** يتطلب تسجيل دخول المستخدم عبر Clerk. إذا أردت إضافة بيانات بدون مصادقة (مثلاً seed script)، ستحتاج إنشاء endpoint خاص أو استخدام Prisma مباشرة.

### بديل: Seed Script مباشر

أنشئ ملف `prisma/seed-kazima.ts`:

```typescript
import { PrismaClient } from '@prisma/client'

const prisma = new PrismaClient()

async function main() {
  const documents = [
    {
      title: 'تاريخ حكام الكويت',
      content: '...',
      source: 'كتاب ...',
      category: 'تاريخ سياسي',
      tags: ['الكويت'],
    },
    // أضف المزيد
  ]

  for (const doc of documents) {
    await prisma.kazimaDocument.create({ data: doc })
  }

  console.log(`تمت إضافة ${documents.length} وثيقة`)
}

main().finally(() => prisma.$disconnect())
```

شغّله:
```bash
npx ts-node --compiler-options '{"module":"CommonJS"}' prisma/seed-kazima.ts
```

**التوصية:** ابدأ بـ 20-50 نص تجريبي لاختبار المحادثة والبحث.

---

## الخطوة 5: فهم تدفق البيانات

### تدفق التحليل البسيط

```
المستخدم → KazimaInput.tsx
  ↓ اختيار الوضع + إدخال النص
  ↓ fetch POST /api/kazima-ai
  ↓
route.ts
  ↓ validateKazimaRequest() — فحص المدخلات
  ↓ cleanForLLM() — تنظيف المسافات فقط
  ↓ buildKazimaPrompt() — دمج البرومبت مع النص
  ↓ callLLM() — إرسال للنموذج
  ↓
KazimaResult.tsx ← عرض النتيجة
  ↓ (اختياري) saveKazimaAnalysis() → KazimaAnalysis table
```

### تدفق التحليل الشامل

```
المستخدم → analyze/page.tsx
  ↓ إدخال النص
  ↓ fetch POST /api/kazima-ai/analyze-full
  ↓
analyze-full/route.ts
  ↓ cleanForLLM()
  ↓ Promise.all([           ← 4 طلبات متوازية
  │   callLLMJson(ENTITIES_PROMPT, text),
  │   callLLMJson(RELATIONS_PROMPT, text),
  │   callLLMJson(TIMELINE_PROMPT, text),
  │   callLLMJson(CLASSIFICATION_PROMPT, text),
  │ ])
  ↓ buildGraph(entities, relations) ← بناء شبكة العلاقات
  ↓
analyze/page.tsx ← عرض في 5 تبويبات: كيانات، علاقات، زمن، تصنيف، شبكة
```

### تدفق المحادثة

```
المستخدم → chat/page.tsx
  ↓ كتابة السؤال
  ↓ fetch POST /api/kazima-ai/chat
  ↓
chat/route.ts
  ↓ cleanForSearch() — تنظيف للبحث
  ↓ prisma.kazimaDocument.findMany() — بحث في قاعدة المعرفة
  ↓ prisma.kazimaAnalysis.findMany() — بحث في التحليلات السابقة
  ↓ بناء السياق من النتائج
  ↓ callLLM(CHAT_SYSTEM_PROMPT, سياق + سؤال)
  ↓
chat/page.tsx ← عرض الإجابة مع المصادر
```

---

## الخطوة 6: فهم معالجة JSON

عند استدعاء `callLLMJson<T>()` (في التحليل الشامل)، النظام يحاول 3 استراتيجيات لقراءة JSON من رد النموذج:

1. **Parse مباشر** — إذا كان الرد JSON نظيف
2. **استخراج من code block** — إذا كان الرد ````json ... ````
3. **Balanced brace matching** — يجد أول `{` ويتتبع الأقواس حتى يكتمل الكائن

إذا فشلت الثلاث، يرمي خطأ واضح.

**تنبيه للمبرمج:** هذه الطريقة تعمل مع أغلب النماذج لكنها ليست مضمونة 100%. إذا واجهت أخطاء JSON متكررة، قد تحتاج:
- استخدام `response_format: { type: "json_object" }` مع OpenAI (مفعّل تلقائيًا)
- أو استخدام Anthropic tool_use بدل text response

---

## الخطوة 7: الصفحات والتنقل

| المسار | الوصف | محمي؟ |
|--------|-------|------|
| `/kazima` | الصفحة الرئيسية — تحليل بسيط + روابط للأدوات | لا |
| `/kazima/analyze` | التحليل الشامل (4 عمليات متوازية) | لا |
| `/kazima/chat` | المحادثة مع قاعدة المعرفة | لا |

**ملاحظة:** الصفحات نفسها ليست محمية، لكن **الحفظ** يتطلب تسجيل دخول.

الروابط مضافة في:
- `components/layout/Header.tsx` — القائمة العلوية (ديسكتوب + موبايل)
- `components/layout/BottomNav.tsx` — القائمة السفلية (موبايل)

---

## الخطوة 8: ما لم يُنجز بعد (Roadmap)

هذه المهام **غير منجزة** ومطلوبة في المراحل التالية:

### أولوية عالية

| المهمة | الوصف | التعقيد |
|--------|-------|---------|
| Deduplication | منع تكرار الكيانات عند إعادة التحليل | منخفض |
| Structured validation | فحص JSON المستخرج ضد schema بدل الثقة المطلقة | متوسط |
| حماية الصفحات | إضافة `/kazima(.*)` لقائمة المسارات المحمية في `middleware.ts` (إذا مطلوب) | منخفض |

### أولوية متوسطة

| المهمة | الوصف | التعقيد |
|--------|-------|---------|
| Embeddings + Vector Search | استبدال البحث اللفظي ببحث دلالي باستخدام pgvector أو Pinecone | عالي |
| واجهة إدارة الوثائق | صفحة لإضافة/تعديل/حذف الوثائق في قاعدة المعرفة | متوسط |
| Citation layer | ربط نتائج التحليل بمراجع فعلية محققة | عالي |

### أولوية منخفضة (مرحلة متقدمة)

| المهمة | الوصف | التعقيد |
|--------|-------|---------|
| Knowledge Graph visualization | رسم تفاعلي لشبكة العلاقات (مثلاً D3.js أو vis.js) | عالي |
| PDF/OCR pipeline | استيراد مخطوطات من PDF مباشرة | عالي |
| Multi-agent analysis | تشغيل عدة نماذج ومقارنة النتائج | عالي |

---

## الخطوة 9: اختبار سريع

### اختبار التحليل البسيط

```bash
curl -X POST http://localhost:3000/api/kazima-ai \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "extraction",
    "text": "ولد الشيخ عبدالله بن خالد آل خليفة في البحرين سنة 1820 وتوفي في الكويت"
  }'
```

### اختبار التحليل الشامل

```bash
curl -X POST http://localhost:3000/api/kazima-ai/analyze-full \
  -H "Content-Type: application/json" \
  -d '{
    "text": "ولد الشيخ عبدالله بن خالد آل خليفة في البحرين سنة 1820 وتوفي في الكويت"
  }'
```

### اختبار المحادثة

```bash
curl -X POST http://localhost:3000/api/kazima-ai/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "من هم حكام الكويت؟"
  }'
```

---

## الخطوة 10: ملاحظات أمنية

1. **مفاتيح API** مخزنة في `.env` فقط — لا تُكشف للمتصفح
2. **أخطاء API** لا تُعرض تفاصيلها للمستخدم — فقط رمز الحالة
3. **الحفظ في قاعدة البيانات** يتطلب مصادقة Clerk
4. **مصطلحات البحث** مُصفّاة (حد أدنى 2 حرف، حد أقصى 10 مصطلحات)
5. **سجل المحادثة** محدود بـ 4 تبادلات و 500 حرف لكل رسالة
6. **النص المُدخل** محدود بـ 50,000 حرف

---

## ملخص التقنيات المستخدمة

| الطبقة | التقنية |
|--------|---------|
| Frontend | Next.js 14 App Router + React 18 + TypeScript |
| Styling | Tailwind CSS (Dark theme + RTL) |
| Database | PostgreSQL via Supabase + Prisma 5 |
| Auth | Clerk |
| LLM | Anthropic Claude API أو OpenAI API |
| Icons | Lucide React |

---

## أوامر مرجعية سريعة

```bash
# التثبيت
npm install

# تهيئة قاعدة البيانات
npx prisma generate
npx prisma db push

# التطوير
npm run dev

# البناء
npm run build

# عرض الجداول
npx prisma studio

# إعادة تهيئة Prisma client بعد تعديل schema
npx prisma generate
npx prisma db push
```
