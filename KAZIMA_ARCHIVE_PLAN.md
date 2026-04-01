# خطة تنفيذ الأرشيف الرقمي — كاظمة (النسخة المعدّلة)

## ما تغيّر عن الخطة الأصلية

| البند الأصلي | التعديل | السبب |
|-------------|---------|-------|
| MySQL + Prisma | **PostgreSQL** (Supabase) | المشروع يستخدم PostgreSQL بالفعل. لا تغيّر قاعدة البيانات |
| أسماء جداول `snake_case` | **PascalCase** (`ArchiveItem`) | للتوافق مع باقي الـ schema (`KazimaAnalysis`, `User`, `Car`) |
| Apache Solr للبحث | **PostgreSQL Full-Text Search** ثم **Meilisearch** لاحقاً | Solr ثقيل جداً لمرحلة مبكرة. PostgreSQL يكفي للبداية |
| `archive_metadata` جدول منفصل (EAV) | **حقول Dublin Core مباشرة على `ArchiveItem`** | EAV يعقّد الاستعلامات بلا فائدة. الحقول ثابتة ومعروفة |
| لم يُحدد مكان تخزين الملفات | **Supabase Storage** (موجود في المشروع) | لا حاجة لإضافة S3 أو خدمة جديدة |
| لم يُذكر نظام الصلاحيات | **Clerk Auth + UserRole ADMIN** | النظام موجود بالفعل. صفحات `/dashboard/archive/*` تتطلب ADMIN |

---

## بنية قاعدة البيانات (تمت إضافتها فعلاً)

الجداول التالية أُضيفت إلى `prisma/schema.prisma`:

### الجداول الأساسية

```
ArchiveItem          العنصر الأرشيفي (كتاب، مخطوطة، وثيقة، صوت، مرئي...)
ArchiveFile          ملفات مرتبطة بعنصر (PDF، صور، صوت، فيديو)
ArchiveOcrPage       نص OCR لكل صفحة من ملف
ArchivePerson        أشخاص (مؤلفين، محققين، ناسخين)
ArchiveSubject       موضوعات (تاريخ سياسي، فقه، تراجم...)
ArchiveCollection    مجموعات (مكتبة الخليفة، أرشيف الكويت...)
```

### جداول الربط (Many-to-Many)

```
ArchiveItemPerson    ربط عنصر بشخص مع تحديد الدور (مؤلف/محقق/ناسخ)
ArchiveItemSubject   ربط عنصر بموضوع
```

### الأنواع (Enums)

```
ArchiveItemType     ARTICLE | BOOK | MANUSCRIPT | DOCUMENT | IMAGE | AUDIO | VIDEO | PUBLICATION
ArchiveItemStatus   DRAFT | REVIEW | PUBLISHED | ARCHIVED
OcrStatus           PENDING | PROCESSING | COMPLETED | FAILED
```

### حقول Dublin Core على ArchiveItem

```
creator             المؤلف / الناسخ
contributor          المحقق / المراجع
publisher            الناشر
identifier           ISBN أو رقم فهرس
sourceReference      المصدر الأصلي
rightsStatement      حقوق النشر
publicationYear      سنة النشر
coveragePlace        التغطية الجغرافية
coveragePeriod       التغطية الزمنية
```

### حقول خاصة بكاظمة

```
collectionName       اسم المجموعة
kuwaitPeriod         الفترة الكويتية
manuscriptNotes      ملاحظات المخطوطة
verificationStatus   محقق / غير محقق / قيد التحقيق
```

---

## هيكل الصفحات (تم إنشاء المجلدات فعلاً)

### صفحات عامة

```
app/archive/page.tsx                    الصفحة الرئيسية — تصفح العناصر
app/archive/search/page.tsx             بحث متقدم مع فلاتر
app/archive/item/[slug]/page.tsx        صفحة العنصر التفصيلية
app/archive/collections/page.tsx        قائمة المجموعات
app/archive/people/page.tsx             قائمة الأشخاص
```

### صفحات الإدارة (تتطلب ADMIN)

```
app/dashboard/archive/items/page.tsx    إدارة العناصر (إضافة/تعديل/حذف)
app/dashboard/archive/import/page.tsx   استيراد عناصر جماعي
```

### واجهات API

```
app/api/archive/route.ts               GET تصفح + POST إضافة عنصر
app/api/archive/search/route.ts         GET بحث متقدم
app/api/archive/[id]/route.ts           GET/PUT/DELETE عنصر واحد
app/api/archive/[id]/files/route.ts     GET/POST ملفات عنصر
app/api/archive/[id]/ocr/route.ts       POST تشغيل OCR
app/api/archive/[id]/ai/route.ts        POST تحليل بالذكاء الاصطناعي
app/api/archive/upload/route.ts         POST رفع ملف إلى Supabase Storage
app/api/archive/reindex/route.ts        POST إعادة بناء search_text
```

---

## تدفق البيانات

### رفع عنصر جديد

```
المدير → dashboard/archive/items
  ↓ يملأ البيانات الأساسية (عنوان، نوع، مؤلف، وصف)
  ↓ POST /api/archive → ArchiveItem.create()
  ↓ يرفع الملفات (PDF / صور)
  ↓ POST /api/archive/upload → Supabase Storage → ArchiveFile.create()
  ↓ (اختياري) يضغط "OCR"
  ↓ POST /api/archive/[id]/ocr → Azure Vision → ArchiveOcrPage.create()
  ↓ يُبنى search_text تلقائياً
  ↓ يغيّر الحالة إلى PUBLISHED
```

### البحث

```
الباحث → /archive/search
  ↓ يكتب كلمة + يختار فلاتر (نوع، فترة، مؤلف)
  ↓ GET /api/archive/search?q=...&type=...&year=...
  ↓
  ↓ المرحلة 1: PostgreSQL ILIKE على search_text
  ↓ المرحلة 2 (لاحقاً): PostgreSQL to_tsvector / to_tsquery
  ↓ المرحلة 3 (متقدم): Meilisearch مع فلاتر عربية
  ↓
  ↓ النتائج ← صفحة البحث
```

### ربط Kazima AI بالأرشيف

```
الباحث → /archive/item/[slug]
  ↓ يضغط "حلل هذا العنصر"
  ↓ يأخذ searchText أو ocrText من ArchiveItem
  ↓ POST /api/archive/[id]/ai
  ↓ يستدعي callLLMJson() من kazima-llm.ts
  ↓ يعرض: كيانات + علاقات + زمن + تصنيف
  ↓ (اختياري) يحفظ النتائج في KazimaAnalysis
```

---

## بناء حقل search_text

يُبنى تلقائياً عند حفظ/تعديل العنصر:

```typescript
function buildSearchText(item: ArchiveItem, ocrPages: ArchiveOcrPage[]): string {
  const parts = [
    item.titleAr,
    item.titleEn,
    item.descriptionAr,
    item.creator,
    item.contributor,
    item.publisher,
    item.collectionName,
    item.tags?.join(' '),
    ...ocrPages.map(p => p.ocrText),
  ]
  return cleanForSearch(parts.filter(Boolean).join(' '))
}
```

---

## OCR — Azure AI Vision

### متغيرات البيئة المطلوبة

```env
AZURE_VISION_ENDPOINT=https://your-resource.cognitiveservices.azure.com
AZURE_VISION_KEY=your-key-here
```

### متى يُستخدم

- ملفات PDF ممسوحة (scanned)
- صور مخطوطات
- وثائق قديمة مصورة

### ما يُخزّن

- نص كل صفحة → `ArchiveOcrPage.ocrText`
- درجة الثقة → `ArchiveOcrPage.confidence`
- حالة المعالجة → `ArchiveOcrPage.ocrStatus`
- بعد OCR: `ArchiveItem.hasOcr = true` + يُحدَّث `searchText`

---

## الصلاحيات

| الصفحة | المستخدم العادي | المدير (ADMIN) |
|--------|----------------|----------------|
| `/archive` | عرض فقط | عرض |
| `/archive/item/[slug]` | عرض + تحميل | عرض + تحميل + تعديل |
| `/archive/search` | بحث | بحث |
| `/dashboard/archive/*` | ممنوع | وصول كامل |
| أزرار Kazima AI | متاح | متاح |

التنفيذ: فحص `UserRole` في middleware أو في الـ Server Action.

---

## Backlog التنفيذ اليومي — المرحلة 1

### اليوم 1: البنية التحتية

```
□ تشغيل npx prisma generate && npx prisma db push
□ إنشاء actions/archiveActions.ts (CRUD أساسي)
□ إنشاء app/api/archive/route.ts (GET browse + POST create)
□ اختبار إضافة عنصر واسترجاعه بـ curl
```

### اليوم 2: صفحة التصفح

```
□ بناء app/archive/page.tsx — شبكة عناصر مع فلاتر نوع
□ إنشاء components/archive/ArchiveCard.tsx — بطاقة عنصر
□ إنشاء components/archive/ArchiveFilters.tsx — فلتر نوع + فترة
□ تصميم RTL + dark theme متوافق مع باقي الموقع
```

### اليوم 3: صفحة العنصر

```
□ بناء app/archive/item/[slug]/page.tsx
□ عرض: العنوان، الوصف، المؤلف، الملفات، بيانات Dublin Core
□ زر تحميل الملف الأساسي
□ إنشاء components/archive/ArchiveItemDetail.tsx
□ إنشاء components/archive/ArchiveFileList.tsx
```

### اليوم 4: استيراد البيانات

```
□ إنشاء prisma/seed-archive.ts مع 25 عنصر تجريبي
□ تشغيل السيد وملء البيانات
□ التأكد أن صفحة التصفح تعرض البيانات
□ التأكد أن صفحة العنصر تعمل بالـ slug
```

### اليوم 5: البحث الأساسي

```
□ بناء app/api/archive/search/route.ts — ILIKE على searchText
□ بناء app/archive/search/page.tsx
□ إضافة شريط بحث في صفحة /archive
□ ربط الفلاتر بالبحث (نوع + فترة + مؤلف)
```

### اليوم 6: رفع الملفات + Dashboard

```
□ بناء app/api/archive/upload/route.ts — رفع إلى Supabase Storage
□ بناء app/dashboard/archive/items/page.tsx — قائمة + إضافة + تعديل
□ التأكد من فحص صلاحية ADMIN
□ اختبار رفع PDF وعرضه في صفحة العنصر
```

---

## Backlog التنفيذ — المرحلة 2 (بعد إطلاق المرحلة 1)

```
□ إضافة ArchivePerson CRUD + صفحة /archive/people
□ إضافة ArchiveSubject CRUD + صفحة /archive/subjects
□ إضافة ArchiveCollection CRUD + صفحة /archive/collections
□ ترقية البحث إلى PostgreSQL to_tsvector (Full-Text)
□ إضافة فلاتر: مؤلف، موضوع، مجموعة، لغة
□ إضافة pagination مع infinite scroll أو numbered pages
□ بناء صفحة /dashboard/archive/import لاستيراد CSV/JSON
```

---

## Backlog التنفيذ — المرحلة 3 (OCR)

```
□ إضافة AZURE_VISION_ENDPOINT + AZURE_VISION_KEY إلى .env
□ بناء lib/archive-ocr.ts — استدعاء Azure Vision API
□ بناء app/api/archive/[id]/ocr/route.ts
□ بناء app/dashboard/archive/ocr/page.tsx — لوحة حالة OCR
□ تشغيل OCR على 5 ملفات تجريبية
□ تحديث searchText بعد OCR
□ اختبار البحث داخل نص OCR
```

---

## Backlog التنفيذ — المرحلة 4 (ربط Kazima AI)

```
□ بناء app/api/archive/[id]/ai/route.ts
□ إضافة زر "حلل هذا العنصر" في صفحة العنصر
□ إضافة زر "استخرج الكيانات" → يستدعي analyze-full
□ إضافة زر "أنشئ بطاقة وصف" → يستدعي publication mode
□ عرض نتائج التحليل داخل صفحة العنصر
□ حفظ النتائج في KazimaAnalysis مع ربطها بـ ArchiveItem.id
```

---

## ملاحظات أمنية

1. **رفع الملفات**: فحص MIME type + حد حجم (50MB للملفات العادية، 500MB للفيديو)
2. **OCR**: لا تشغّل OCR على أكثر من 5 ملفات بالتوازي (حد Azure)
3. **البحث**: تنظيف مصطلحات البحث بـ `cleanForSearch()` الموجودة
4. **الصلاحيات**: كل عمليات الكتابة تتطلب ADMIN
5. **الـ Slugs**: تُولّد من العنوان العربي مع transliteration أو UUID مختصر

---

## أوامر مرجعية

```bash
# تطبيق schema الأرشيف
npx prisma generate
npx prisma db push

# تشغيل السيد
npx ts-node --compiler-options '{"module":"CommonJS"}' prisma/seed-archive.ts

# عرض الجداول
npx prisma studio

# تطوير
npm run dev
```

---

## العلاقة بين الأرشيف وكاظمة AI

```
                    ┌─────────────────────┐
                    │   kazima.org/archive │
                    │   (الأرشيف الرقمي)   │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
     ArchiveItem          ArchiveFile      ArchiveOcrPage
     (البيانات)           (الملفات)        (نص OCR)
              │                                 │
              └──────────┬──────────────────────┘
                         │ searchText
                         ▼
              ┌──────────────────────┐
              │    Kazima AI Layer   │
              │  (تحليل + استخراج)    │
              └──────────┬───────────┘
                         │
           ┌─────────────┼─────────────┐
           │             │             │
    KazimaAnalysis  KazimaGraphData  KazimaDocument
    (نتائج التحليل)  (شبكة العلاقات)  (قاعدة المعرفة)
```

الأرشيف = المحتوى. كاظمة AI = الذكاء فوق المحتوى.
KazimaDocument يبقى كقاعدة معرفة مستقلة للمحادثة. لا يتداخل مع ArchiveItem.
