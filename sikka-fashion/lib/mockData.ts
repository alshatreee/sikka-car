export interface MockFashionItem {
  id: string;
  title: string;
  titleAr: string;
  brand: string;
  category: string;
  size: string;
  color: string;
  condition: string;
  occasion: string;
  retailPrice: number;
  listingType: "RENT" | "SALE" | "BOTH";
  rentalPricePerDay: number | null;
  salePrice: number | null;
  cleaningFee: number | null;
  images: string[];
  area: string;
  ownerName: string;
  rating: number;
  reviewCount: number;
}

export const mockItems: MockFashionItem[] = [
  {
    id: "1",
    title: "Taller Marmo Gold Evening Dress",
    titleAr: "فستان سهرة تالر مارمو ذهبي",
    brand: "Taller Marmo",
    category: "EVENING_GOWN",
    size: "M",
    color: "ذهبي",
    condition: "EXCELLENT",
    occasion: "WEDDING",
    retailPrice: 450,
    listingType: "RENT",
    rentalPricePerDay: 35,
    salePrice: null,
    cleaningFee: 5,
    images: ["/images/placeholder-dress-1.jpg"],
    area: "السالمية",
    ownerName: "نورة الصباح",
    rating: 4.8,
    reviewCount: 12,
  },
  {
    id: "2",
    title: "Meshki Black Power Suit",
    titleAr: "بدلة ميشكي سوداء أنيقة",
    brand: "Meshki",
    category: "SUIT",
    size: "S",
    color: "أسود",
    condition: "NEW_WITH_TAGS",
    occasion: "BUSINESS",
    retailPrice: 280,
    listingType: "BOTH",
    rentalPricePerDay: 20,
    salePrice: 180,
    cleaningFee: 3,
    images: ["/images/placeholder-suit-1.jpg"],
    area: "حولي",
    ownerName: "دانة المطيري",
    rating: 4.9,
    reviewCount: 8,
  },
  {
    id: "3",
    title: "Retrofete Sequin Party Dress",
    titleAr: "فستان ريتروفيت سيكوين للحفلات",
    brand: "Retrofete",
    category: "DRESS",
    size: "L",
    color: "فضي",
    condition: "VERY_GOOD",
    occasion: "PARTY",
    retailPrice: 380,
    listingType: "RENT",
    rentalPricePerDay: 30,
    salePrice: null,
    cleaningFee: 5,
    images: ["/images/placeholder-dress-2.jpg"],
    area: "الشويخ",
    ownerName: "ليلى الخالد",
    rating: 4.7,
    reviewCount: 15,
  },
  {
    id: "4",
    title: "Zara Premium Blazer Set",
    titleAr: "طقم بلايزر زارا بريميوم",
    brand: "Zara",
    category: "BLAZER",
    size: "M",
    color: "بيج",
    condition: "EXCELLENT",
    occasion: "FORMAL",
    retailPrice: 120,
    listingType: "SALE",
    rentalPricePerDay: null,
    salePrice: 65,
    cleaningFee: null,
    images: ["/images/placeholder-blazer-1.jpg"],
    area: "العاصمة",
    ownerName: "فاطمة العنزي",
    rating: 4.5,
    reviewCount: 6,
  },
  {
    id: "5",
    title: "Elie Saab Engagement Gown",
    titleAr: "فستان خطوبة إيلي صعب",
    brand: "Elie Saab",
    category: "EVENING_GOWN",
    size: "S",
    color: "وردي",
    condition: "EXCELLENT",
    occasion: "ENGAGEMENT",
    retailPrice: 1200,
    listingType: "RENT",
    rentalPricePerDay: 80,
    salePrice: null,
    cleaningFee: 8,
    images: ["/images/placeholder-gown-1.jpg"],
    area: "السالمية",
    ownerName: "هيا الرشيد",
    rating: 5.0,
    reviewCount: 20,
  },
  {
    id: "6",
    title: "Designer Abaya with Gold Embroidery",
    titleAr: "عباية مصممة بتطريز ذهبي",
    brand: "Bambah",
    category: "ABAYA",
    size: "L",
    color: "أسود وذهبي",
    condition: "NEW_WITH_TAGS",
    occasion: "EID",
    retailPrice: 350,
    listingType: "BOTH",
    rentalPricePerDay: 25,
    salePrice: 220,
    cleaningFee: 4,
    images: ["/images/placeholder-abaya-1.jpg"],
    area: "الجابرية",
    ownerName: "مريم الهاجري",
    rating: 4.6,
    reviewCount: 9,
  },
  {
    id: "7",
    title: "Self-Portrait Lace Midi Dress",
    titleAr: "فستان سيلف بورتريت دانتيل ميدي",
    brand: "Self-Portrait",
    category: "DRESS",
    size: "XS",
    color: "أبيض",
    condition: "VERY_GOOD",
    occasion: "GRADUATION",
    retailPrice: 320,
    listingType: "SALE",
    rentalPricePerDay: null,
    salePrice: 160,
    cleaningFee: null,
    images: ["/images/placeholder-dress-3.jpg"],
    area: "المنقف",
    ownerName: "سارة الفضلي",
    rating: 4.4,
    reviewCount: 5,
  },
  {
    id: "8",
    title: "Alexander McQueen Tailored Suit",
    titleAr: "بدلة ألكسندر ماكوين مفصلة",
    brand: "Alexander McQueen",
    category: "SUIT",
    size: "M",
    color: "كحلي",
    condition: "EXCELLENT",
    occasion: "FORMAL",
    retailPrice: 950,
    listingType: "RENT",
    rentalPricePerDay: 55,
    salePrice: null,
    cleaningFee: 7,
    images: ["/images/placeholder-suit-2.jpg"],
    area: "الشويخ",
    ownerName: "عائشة البدر",
    rating: 4.9,
    reviewCount: 18,
  },
];

export function getItemsByType(type: "RENT" | "SALE") {
  return mockItems.filter(
    (item) => item.listingType === type || item.listingType === "BOTH"
  );
}

export function getItemById(id: string) {
  return mockItems.find((item) => item.id === id);
}
