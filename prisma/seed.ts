import { PrismaClient } from '@prisma/client'

const prisma = new PrismaClient()

async function main() {
  console.log('🌱 Seeding database...')

  // Create a demo owner user
  const demoUser = await prisma.user.upsert({
    where: { clerkUserId: 'demo_owner_001' },
    update: {},
    create: {
      clerkUserId: 'demo_owner_001',
      email: 'demo@sikkacar.com',
      fullName: 'سكة كار',
      phone: '+96512345678',
    },
  })

  console.log('✅ Demo user created:', demoUser.id)

  // Sample cars data
  const carsData = [
    {
      title: 'تويوتا كامري 2024 فل كامل',
      brand: 'Toyota',
      model: 'Camry',
      year: 2024,
      dailyPrice: 18,
      area: 'العاصمة',
      city: 'الكويت',
      origin: 'وكالة',
      type: 'سيدان',
      category: 'اقتصادي',
      seats: 5,
      transmission: 'AUTOMATIC' as const,
      smokingPolicy: 'ممنوع التدخين',
      distancePolicy: '200 كم يومياً',
      minAge: 21,
      availabilityText: 'متاح يومياً',
      images: [
        'https://images.unsplash.com/photo-1621007947382-bb3c3994e3fb?w=800&h=500&fit=crop',
      ],
    },
    {
      title: 'نيسان باترول بلاتينيوم 2023',
      brand: 'Nissan',
      model: 'Patrol',
      year: 2023,
      dailyPrice: 35,
      area: 'حولي',
      city: 'السالمية',
      origin: 'وكالة',
      type: 'SUV',
      category: 'فاخر',
      seats: 7,
      transmission: 'AUTOMATIC' as const,
      smokingPolicy: 'ممنوع التدخين',
      distancePolicy: '250 كم يومياً',
      minAge: 25,
      availabilityText: 'متاح يومياً',
      images: [
        'https://images.unsplash.com/photo-1609521263047-f8f205293f24?w=800&h=500&fit=crop',
      ],
    },
    {
      title: 'لكزس ES 350 موديل 2024',
      brand: 'Lexus',
      model: 'ES 350',
      year: 2024,
      dailyPrice: 28,
      area: 'الفروانية',
      city: 'الفروانية',
      origin: 'وكالة',
      type: 'سيدان',
      category: 'فاخر',
      seats: 5,
      transmission: 'AUTOMATIC' as const,
      smokingPolicy: 'ممنوع التدخين',
      distancePolicy: '200 كم يومياً',
      minAge: 23,
      availabilityText: 'متاح من السبت للخميس',
      images: [
        'https://images.unsplash.com/photo-1606611013016-969c19ba27d5?w=800&h=500&fit=crop',
      ],
    },
    {
      title: 'شيفروليه تاهو 2023 LT',
      brand: 'Chevrolet',
      model: 'Tahoe',
      year: 2023,
      dailyPrice: 30,
      area: 'الأحمدي',
      city: 'المنقف',
      origin: 'وكالة',
      type: 'SUV',
      category: 'عائلي',
      seats: 8,
      transmission: 'AUTOMATIC' as const,
      smokingPolicy: 'ممنوع التدخين',
      distancePolicy: '300 كم يومياً',
      minAge: 25,
      availabilityText: 'متاح يومياً',
      images: [
        'https://images.unsplash.com/photo-1533473359331-0135ef1b58bf?w=800&h=500&fit=crop',
      ],
    },
    {
      title: 'كيا K5 موديل 2024 GT Line',
      brand: 'Kia',
      model: 'K5',
      year: 2024,
      dailyPrice: 15,
      area: 'الجهراء',
      city: 'الجهراء',
      origin: 'وكالة',
      type: 'سيدان',
      category: 'اقتصادي',
      seats: 5,
      transmission: 'AUTOMATIC' as const,
      smokingPolicy: 'مسموح بالتدخين',
      distancePolicy: '200 كم يومياً',
      minAge: 21,
      availabilityText: 'متاح يومياً',
      images: [
        'https://images.unsplash.com/photo-1552519507-da3b142c6e3d?w=800&h=500&fit=crop',
      ],
    },
    {
      title: 'مرسيدس C200 كوبيه 2023',
      brand: 'Mercedes',
      model: 'C200',
      year: 2023,
      dailyPrice: 40,
      area: 'العاصمة',
      city: 'شرق',
      origin: 'وكالة',
      type: 'كوبيه',
      category: 'رياضي',
      seats: 4,
      transmission: 'AUTOMATIC' as const,
      smokingPolicy: 'ممنوع التدخين',
      distancePolicy: '150 كم يومياً',
      minAge: 25,
      availabilityText: 'متاح نهاية الأسبوع',
      images: [
        'https://images.unsplash.com/photo-1618843479313-40f8afb4b4d8?w=800&h=500&fit=crop',
      ],
    },
    {
      title: 'هيونداي توسان 2024 بانوراما',
      brand: 'Hyundai',
      model: 'Tucson',
      year: 2024,
      dailyPrice: 20,
      area: 'مبارك الكبير',
      city: 'صباح السالم',
      origin: 'وكالة',
      type: 'SUV',
      category: 'عائلي',
      seats: 5,
      transmission: 'AUTOMATIC' as const,
      smokingPolicy: 'ممنوع التدخين',
      distancePolicy: '250 كم يومياً',
      minAge: 21,
      availabilityText: 'متاح يومياً',
      images: [
        'https://images.unsplash.com/photo-1580273916550-e323be2ae537?w=800&h=500&fit=crop',
      ],
    },
    {
      title: 'تويوتا لاندكروزر VXR 2024',
      brand: 'Toyota',
      model: 'Land Cruiser',
      year: 2024,
      dailyPrice: 50,
      area: 'حولي',
      city: 'حولي',
      origin: 'وكالة',
      type: 'SUV',
      category: 'فاخر',
      seats: 7,
      transmission: 'AUTOMATIC' as const,
      smokingPolicy: 'ممنوع التدخين',
      distancePolicy: '300 كم يومياً',
      minAge: 25,
      availabilityText: 'متاح يومياً',
      images: [
        'https://images.unsplash.com/photo-1519641471654-76ce0107ad1b?w=800&h=500&fit=crop',
      ],
    },
  ]

  // Create cars
  for (const carData of carsData) {
    await prisma.car.create({
      data: {
        ...carData,
        ownerId: demoUser.id,
        status: 'APPROVED',
        documentImages: [],
      },
    })
  }

  console.log(`✅ ${carsData.length} sample cars created (APPROVED status)`)
  console.log('🎉 Seeding complete!')
}

main()
  .catch((e) => {
    console.error('❌ Seed error:', e)
    process.exit(1)
  })
  .finally(async () => {
    await prisma.$disconnect()
  })
