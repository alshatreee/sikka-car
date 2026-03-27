import { PrismaClient, CarStatus, UserRole, TransmissionType } from "@prisma/client";

const prisma = new PrismaClient();

async function main() {
  console.log("🌱 Starting seed...");

  // Upsert demo user
  const user = await prisma.user.upsert({
    where: { clerkUserId: "demo_owner_001" },
    update: {},
    create: {
      clerkUserId: "demo_owner_001",
      email: "demo@sikkacar.com",
      fullName: "أحمد المطيري",
      role: UserRole.USER,
      phone: "+96550000001",
    },
  });
  console.log(`✅ User upserted: ${user.fullName} (${user.id})`);

  // Sample cars
  const cars = [
    {
      title: "تويوتا كامري 2024 فل كامل",
      titleEn: "Toyota Camry 2024 Full Option",
      brand: "Toyota",
      model: "Camry",
      year: 2024,
      dailyPrice: 12,
      area: "العاصمة",
      city: "الكويت",
      category: "سيدان",
      type: "عائلية",
      seats: 5,
      transmission: TransmissionType.AUTOMATIC,
      images: [
        "https://picsum.photos/seed/car1/800/500",
        "https://picsum.photos/seed/car1b/800/500",
      ],
    },
    {
      title: "نيسان باترول 2023 بلاتينيوم",
      titleEn: "Nissan Patrol 2023 Platinum",
      brand: "Nissan",
      model: "Patrol",
      year: 2023,
      dailyPrice: 25,
      area: "حولي",
      city: "السالمية",
      category: "دفع رباعي",
      type: "فاخرة",
      seats: 7,
      transmission: TransmissionType.AUTOMATIC,
      images: [
        "https://picsum.photos/seed/car2/800/500",
        "https://picsum.photos/seed/car2b/800/500",
      ],
    },
    {
      title: "هيونداي توسان 2025 نص فل",
      titleEn: "Hyundai Tucson 2025 Mid Option",
      brand: "Hyundai",
      model: "Tucson",
      year: 2025,
      dailyPrice: 10,
      area: "الفروانية",
      city: "الفروانية",
      category: "دفع رباعي",
      type: "عائلية",
      seats: 5,
      transmission: TransmissionType.AUTOMATIC,
      images: [
        "https://picsum.photos/seed/car3/800/500",
        "https://picsum.photos/seed/car3b/800/500",
      ],
    },
    {
      title: "كيا سيراتو 2022 اقتصادية",
      titleEn: "Kia Cerato 2022 Economy",
      brand: "Kia",
      model: "Cerato",
      year: 2022,
      dailyPrice: 7,
      area: "الأحمدي",
      city: "الفحيحيل",
      category: "سيدان",
      type: "اقتصادية",
      seats: 5,
      transmission: TransmissionType.AUTOMATIC,
      images: [
        "https://picsum.photos/seed/car4/800/500",
        "https://picsum.photos/seed/car4b/800/500",
      ],
    },
    {
      title: "شيفروليه تاهو 2023 LT",
      titleEn: "Chevrolet Tahoe 2023 LT",
      brand: "Chevrolet",
      model: "Tahoe",
      year: 2023,
      dailyPrice: 22,
      area: "العاصمة",
      city: "الشويخ",
      category: "دفع رباعي",
      type: "فاخرة",
      seats: 7,
      transmission: TransmissionType.AUTOMATIC,
      images: [
        "https://picsum.photos/seed/car5/800/500",
        "https://picsum.photos/seed/car5b/800/500",
      ],
    },
    {
      title: "تويوتا يارس 2021 هاتشباك",
      titleEn: "Toyota Yaris 2021 Hatchback",
      brand: "Toyota",
      model: "Yaris",
      year: 2021,
      dailyPrice: 5,
      area: "حولي",
      city: "حولي",
      category: "هاتشباك",
      type: "اقتصادية",
      seats: 5,
      transmission: TransmissionType.AUTOMATIC,
      images: [
        "https://picsum.photos/seed/car6/800/500",
        "https://picsum.photos/seed/car6b/800/500",
      ],
    },
    {
      title: "لكزس ES 2024 هايبرد",
      titleEn: "Lexus ES 2024 Hybrid",
      brand: "Lexus",
      model: "ES",
      year: 2024,
      dailyPrice: 18,
      area: "الفروانية",
      city: "الرقعي",
      category: "سيدان",
      type: "فاخرة",
      seats: 5,
      transmission: TransmissionType.AUTOMATIC,
      images: [
        "https://picsum.photos/seed/car7/800/500",
        "https://picsum.photos/seed/car7b/800/500",
      ],
    },
    {
      title: "فورد اكسبلورر 2020 XLT",
      titleEn: "Ford Explorer 2020 XLT",
      brand: "Ford",
      model: "Explorer",
      year: 2020,
      dailyPrice: 15,
      area: "الأحمدي",
      city: "المنقف",
      category: "دفع رباعي",
      type: "عائلية",
      seats: 7,
      transmission: TransmissionType.AUTOMATIC,
      images: [
        "https://picsum.photos/seed/car8/800/500",
        "https://picsum.photos/seed/car8b/800/500",
      ],
    },
  ];

  for (const car of cars) {
    const created = await prisma.car.create({
      data: {
        ownerId: user.id,
        title: car.title,
        titleEn: car.titleEn,
        brand: car.brand,
        model: car.model,
        year: car.year,
        dailyPrice: car.dailyPrice,
        area: car.area,
        city: car.city,
        category: car.category,
        type: car.type,
        seats: car.seats,
        transmission: car.transmission,
        images: car.images,
        documentImages: [],
        status: CarStatus.APPROVED,
        smokingPolicy: "ممنوع التدخين",
        distancePolicy: "غير محدود",
        minAge: 21,
        availabilityText: "متاح يومياً",
      },
    });
    console.log(`✅ Car created: ${created.title} (${created.id})`);
  }

  console.log(`\n🌱 Seed complete: 1 user + ${cars.length} cars`);
}

main()
  .then(async () => {
    await prisma.$disconnect();
  })
  .catch(async (e) => {
    console.error("❌ Seed failed:", e);
    await prisma.$disconnect();
    process.exit(1);
  });
