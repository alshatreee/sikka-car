import { PrismaClient } from '@prisma/client'

const prisma = new PrismaClient()

async function main() {
  console.log('بدء تعبئة بيانات الأرشيف...')

  // ===== Subjects =====
  const subjects = await Promise.all([
    prisma.archiveSubject.create({ data: { nameAr: 'تاريخ سياسي', nameEn: 'Political History', slug: 'political-history' } }),
    prisma.archiveSubject.create({ data: { nameAr: 'تاريخ ديني', nameEn: 'Religious History', slug: 'religious-history' } }),
    prisma.archiveSubject.create({ data: { nameAr: 'تراجم وطبقات', nameEn: 'Biographies', slug: 'biographies' } }),
    prisma.archiveSubject.create({ data: { nameAr: 'فقه وأصوله', nameEn: 'Fiqh', slug: 'fiqh' } }),
    prisma.archiveSubject.create({ data: { nameAr: 'أنساب وقبائل', nameEn: 'Genealogy & Tribes', slug: 'genealogy' } }),
    prisma.archiveSubject.create({ data: { nameAr: 'جغرافيا ورحلات', nameEn: 'Geography & Travel', slug: 'geography' } }),
    prisma.archiveSubject.create({ data: { nameAr: 'وثائق وأرشيف', nameEn: 'Documents & Archives', slug: 'documents' } }),
    prisma.archiveSubject.create({ data: { nameAr: 'أدب ولغة', nameEn: 'Literature & Language', slug: 'literature' } }),
  ])

  console.log(`تمت إضافة ${subjects.length} موضوع`)

  // ===== People =====
  const people = await Promise.all([
    prisma.archivePerson.create({ data: { nameAr: 'عبدالله بن خالد آل خليفة', nameEn: 'Abdullah bin Khalid Al Khalifa', slug: 'abdullah-alkhalifa', birthYear: 1820 } }),
    prisma.archivePerson.create({ data: { nameAr: 'يوسف بن عيسى القناعي', nameEn: 'Yusuf bin Isa Al-Qinai', slug: 'yusuf-alqinai', birthYear: 1879, deathYear: 1973 } }),
    prisma.archivePerson.create({ data: { nameAr: 'عبدالعزيز الرشيد', nameEn: 'Abdulaziz Al-Rashid', slug: 'abdulaziz-alrashid', birthYear: 1887, deathYear: 1938 } }),
    prisma.archivePerson.create({ data: { nameAr: 'خالد الفرج', nameEn: 'Khalid Al-Faraj', slug: 'khalid-alfaraj', birthYear: 1898, deathYear: 1954 } }),
    prisma.archivePerson.create({ data: { nameAr: 'أحمد البشر الرومي', nameEn: 'Ahmad Al-Bishr Al-Rumi', slug: 'ahmad-alrumi', birthYear: 1920, deathYear: 2009 } }),
  ])

  console.log(`تمت إضافة ${people.length} شخص`)

  // ===== Collections =====
  const collections = await Promise.all([
    prisma.archiveCollection.create({ data: { nameAr: 'مكتبة الكتب والمخطوطات', nameEn: 'Books & Manuscripts', slug: 'books-manuscripts', descriptionAr: 'مجموعة الكتب المطبوعة والمخطوطات التراثية', itemCount: 0 } }),
    prisma.archiveCollection.create({ data: { nameAr: 'الأرشيف المرئي', nameEn: 'Visual Archive', slug: 'visual-archive', descriptionAr: 'صور ومقاطع مرئية تاريخية', itemCount: 0 } }),
    prisma.archiveCollection.create({ data: { nameAr: 'الوثائق التاريخية', nameEn: 'Historical Documents', slug: 'historical-documents', descriptionAr: 'وثائق رسمية ومراسلات تاريخية', itemCount: 0 } }),
  ])

  console.log(`تمت إضافة ${collections.length} مجموعة`)

  // ===== Archive Items =====
  const items = [
    {
      slug: 'tarikh-alkuwait-alrashid',
      titleAr: 'تاريخ الكويت',
      titleEn: 'History of Kuwait',
      descriptionAr: 'كتاب تاريخ الكويت للمؤرخ عبدالعزيز الرشيد، يُعد من أوائل الكتب المؤلفة في تاريخ الكويت الحديث. يتناول الكتاب تاريخ الكويت منذ تأسيسها حتى أوائل القرن العشرين.',
      itemType: 'BOOK' as const,
      creator: 'عبدالعزيز الرشيد',
      publicationYear: 1926,
      coveragePlace: 'الكويت',
      coveragePeriod: 'القرن 18-20',
      collectionName: 'مكتبة الكتب والمخطوطات',
      verificationStatus: 'محقق',
      tags: ['الكويت', 'تاريخ', 'آل صباح'],
    },
    {
      slug: 'safahat-min-tarikh-alkuwait',
      titleAr: 'صفحات من تاريخ الكويت',
      titleEn: 'Pages from Kuwait History',
      descriptionAr: 'كتاب يوسف بن عيسى القناعي، يضم مجموعة من المقالات والذكريات عن تاريخ الكويت وأعلامها.',
      itemType: 'BOOK' as const,
      creator: 'يوسف بن عيسى القناعي',
      publicationYear: 1946,
      coveragePlace: 'الكويت',
      coveragePeriod: 'القرن 19-20',
      collectionName: 'مكتبة الكتب والمخطوطات',
      verificationStatus: 'محقق',
      tags: ['الكويت', 'ذكريات', 'مجتمع'],
    },
    {
      slug: 'alkhilaqa-walkhilaqa',
      titleAr: 'الخلاقة والخليقة',
      descriptionAr: 'مخطوطة في العقائد والفقه، تعود إلى القرن التاسع عشر.',
      itemType: 'MANUSCRIPT' as const,
      coveragePlace: 'الخليج العربي',
      coveragePeriod: 'القرن 19',
      collectionName: 'مكتبة الكتب والمخطوطات',
      verificationStatus: 'قيد التحقيق',
      tags: ['مخطوطة', 'فقه', 'عقيدة'],
    },
    {
      slug: 'wathiqat-altijara-1899',
      titleAr: 'وثيقة تجارية كويتية 1899',
      descriptionAr: 'وثيقة تجارية أصلية تعود لسنة 1899 تتعلق بالتبادل التجاري بين الكويت والبصرة.',
      itemType: 'DOCUMENT' as const,
      publicationYear: 1899,
      coveragePlace: 'الكويت - البصرة',
      coveragePeriod: 'القرن 19',
      collectionName: 'الوثائق التاريخية',
      tags: ['وثيقة', 'تجارة', 'الكويت', 'البصرة'],
    },
    {
      slug: 'diwan-khalid-alfaraj',
      titleAr: 'ديوان خالد الفرج',
      titleEn: 'Diwan of Khalid Al-Faraj',
      descriptionAr: 'مجموعة أشعار الشاعر الكويتي خالد الفرج، تضم قصائد في الوطنية والاجتماع والحكمة.',
      itemType: 'BOOK' as const,
      creator: 'خالد الفرج',
      publicationYear: 1952,
      coveragePlace: 'الكويت',
      coveragePeriod: 'القرن 20',
      collectionName: 'مكتبة الكتب والمخطوطات',
      verificationStatus: 'محقق',
      tags: ['شعر', 'أدب', 'الكويت'],
    },
  ]

  for (const item of items) {
    await prisma.archiveItem.create({
      data: {
        ...item,
        status: 'PUBLISHED',
        language: 'ar',
        searchText: [item.titleAr, item.titleEn, item.descriptionAr, item.creator].filter(Boolean).join(' '),
      },
    })
  }

  console.log(`تمت إضافة ${items.length} عنصر أرشيفي`)

  // Link items to people and subjects
  const allItems = await prisma.archiveItem.findMany({ select: { id: true, slug: true } })
  const tarikhItem = allItems.find(i => i.slug === 'tarikh-alkuwait-alrashid')
  const safahatItem = allItems.find(i => i.slug === 'safahat-min-tarikh-alkuwait')
  const diwanItem = allItems.find(i => i.slug === 'diwan-khalid-alfaraj')

  if (tarikhItem) {
    await prisma.archiveItemPerson.create({ data: { itemId: tarikhItem.id, personId: people[2].id, role: 'مؤلف' } })
    await prisma.archiveItemSubject.create({ data: { itemId: tarikhItem.id, subjectId: subjects[0].id } })
  }

  if (safahatItem) {
    await prisma.archiveItemPerson.create({ data: { itemId: safahatItem.id, personId: people[1].id, role: 'مؤلف' } })
    await prisma.archiveItemSubject.create({ data: { itemId: safahatItem.id, subjectId: subjects[0].id } })
    await prisma.archiveItemSubject.create({ data: { itemId: safahatItem.id, subjectId: subjects[2].id } })
  }

  if (diwanItem) {
    await prisma.archiveItemPerson.create({ data: { itemId: diwanItem.id, personId: people[3].id, role: 'مؤلف' } })
    await prisma.archiveItemSubject.create({ data: { itemId: diwanItem.id, subjectId: subjects[7].id } })
  }

  console.log('تم ربط العناصر بالأشخاص والموضوعات')
  console.log('✓ انتهت تعبئة بيانات الأرشيف بنجاح')
}

main()
  .catch((e) => {
    console.error('خطأ:', e)
    process.exit(1)
  })
  .finally(() => prisma.$disconnect())
