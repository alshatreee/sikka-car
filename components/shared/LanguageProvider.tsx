'use client'

import { createContext, useContext, useState, useCallback, ReactNode } from 'react'

type Language = 'ar' | 'en'

interface Translations {
  [key: string]: { ar: string; en: string }
}

const translations: Translations = {
  // Navigation
  home: { ar: 'الرئيسية', en: 'Home' },
  browse: { ar: 'تصفح السيارات', en: 'Browse Cars' },
  listCar: { ar: 'أضف سيارتك', en: 'List Your Car' },
  dashboard: { ar: 'لوحة التحكم', en: 'Dashboard' },
  signIn: { ar: 'تسجيل الدخول', en: 'Sign In' },
  signUp: { ar: 'إنشاء حساب', en: 'Sign Up' },
  signOut: { ar: 'تسجيل الخروج', en: 'Sign Out' },

  // Home
  heroTitle: { ar: 'استأجر سيارتك المثالية في الكويت', en: 'Rent Your Perfect Car in Kuwait' },
  heroSubtitle: { ar: 'أكبر منصة لتأجير السيارات بين الأفراد', en: 'The Largest Peer-to-Peer Car Rental Platform' },
  browseNow: { ar: 'تصفح الآن', en: 'Browse Now' },
  listYourCar: { ar: 'أضف سيارتك', en: 'List Your Car' },
  featuredCars: { ar: 'سيارات مميزة', en: 'Featured Cars' },
  whyChooseUs: { ar: 'لماذا سكة كار؟', en: 'Why Sikka Car?' },
  securePayments: { ar: 'دفع آمن', en: 'Secure Payments' },
  securePaymentsDesc: { ar: 'ادفع عبر K-Net أو Visa أو Apple Pay بأمان تام', en: 'Pay securely via K-Net, Visa, or Apple Pay' },
  verifiedCars: { ar: 'سيارات موثوقة', en: 'Verified Cars' },
  verifiedCarsDesc: { ar: 'جميع السيارات تمر بمراجعة دقيقة قبل الإعلان', en: 'All cars are carefully reviewed before listing' },
  easyBooking: { ar: 'حجز سهل', en: 'Easy Booking' },
  easyBookingDesc: { ar: 'احجز سيارتك في دقائق مع تأكيد فوري', en: 'Book your car in minutes with instant confirmation' },

  // Car details
  perDay: { ar: 'د.ك / يوم', en: 'KWD / day' },
  year: { ar: 'السنة', en: 'Year' },
  seats: { ar: 'المقاعد', en: 'Seats' },
  transmission: { ar: 'ناقل الحركة', en: 'Transmission' },
  area: { ar: 'المنطقة', en: 'Area' },
  automatic: { ar: 'أوتوماتيك', en: 'Automatic' },
  manual: { ar: 'عادي', en: 'Manual' },
  electric: { ar: 'كهربائي', en: 'Electric' },
  bookNow: { ar: 'احجز الآن', en: 'Book Now' },
  contactOwner: { ar: 'تواصل مع المالك', en: 'Contact Owner' },

  // Booking
  startDate: { ar: 'تاريخ البداية', en: 'Start Date' },
  endDate: { ar: 'تاريخ النهاية', en: 'End Date' },
  pickupTime: { ar: 'وقت الاستلام', en: 'Pickup Time' },
  dropoffTime: { ar: 'وقت التسليم', en: 'Dropoff Time' },
  additionalNotes: { ar: 'ملاحظات إضافية', en: 'Additional Notes' },
  completeBooking: { ar: 'إكمال الحجز', en: 'Complete Booking' },
  processing: { ar: 'جارٍ المعالجة...', en: 'Processing...' },
  totalAmount: { ar: 'المبلغ الإجمالي', en: 'Total Amount' },

  // Dashboard
  totalCars: { ar: 'إجمالي السيارات', en: 'Total Cars' },
  approved: { ar: 'المعتمدة', en: 'Approved' },
  pendingReview: { ar: 'قيد المراجعة', en: 'Pending Review' },
  rejected: { ar: 'مرفوضة', en: 'Rejected' },
  status: { ar: 'الحالة', en: 'Status' },
  dailyPrice: { ar: 'السعر اليومي', en: 'Daily Price' },
  myBookings: { ar: 'حجوزاتي', en: 'My Bookings' },

  // List car
  carName: { ar: 'اسم السيارة', en: 'Car Name' },
  carImages: { ar: 'صور السيارة', en: 'Car Images' },
  documents: { ar: 'صور المستندات', en: 'Document Images' },
  city: { ar: 'المدينة', en: 'City' },
  origin: { ar: 'بلد المنشأ', en: 'Country of Origin' },
  carType: { ar: 'النوع', en: 'Type' },
  category: { ar: 'الفئة', en: 'Category' },
  smokingPolicy: { ar: 'سياسة التدخين', en: 'Smoking Policy' },
  distancePolicy: { ar: 'سياسة المسافة', en: 'Distance Policy' },
  minAge: { ar: 'الحد الأدنى للعمر', en: 'Minimum Age' },
  availability: { ar: 'التوفر', en: 'Availability' },
  notes: { ar: 'ملاحظات', en: 'Notes' },
  submitting: { ar: 'جارٍ الإرسال...', en: 'Submitting...' },
  submitForReview: { ar: 'إرسال للمراجعة', en: 'Submit for Review' },

  // Filters
  allAreas: { ar: 'جميع المناطق', en: 'All Areas' },
  allTransmissions: { ar: 'جميع الأنواع', en: 'All Transmissions' },
  allCategories: { ar: 'جميع الفئات', en: 'All Categories' },
  search: { ar: 'بحث...', en: 'Search...' },
  filter: { ar: 'تصفية', en: 'Filter' },
  reset: { ar: 'إعادة ضبط', en: 'Reset' },
  noResults: { ar: 'لا توجد نتائج', en: 'No results found' },
  carsAvailable: { ar: 'سيارة متاحة', en: 'cars available' },
  oneCarAvailable: { ar: 'سيارة متاحة', en: 'car available' },
  noResultsTitle: { ar: 'لم يتم العثور على نتائج', en: 'No results found' },
  noResultsHint: { ar: 'جرّب تغيير معايير البحث', en: 'Try changing your search criteria' },
  clearFilters: { ar: 'امسح الفلاتر', en: 'Clear Filters' },
  sortBy: { ar: 'ترتيب حسب', en: 'Sort by' },
  sortNewest: { ar: 'الأحدث', en: 'Newest' },
  sortPriceLow: { ar: 'السعر: الأقل', en: 'Price: Low' },
  sortPriceHigh: { ar: 'السعر: الأعلى', en: 'Price: High' },
  sortYear: { ar: 'الأحدث موديل', en: 'Newest Model' },

  // Payment
  paymentSuccess: { ar: 'تم الدفع بنجاح!', en: 'Payment Successful!' },
  paymentSuccessMsg: { ar: 'شكراً لك، تم تأكيد حجزك بنجاح', en: 'Thank you, your booking has been confirmed' },
  verifyingPayment: { ar: 'جاري التحقق من الدفع...', en: 'Verifying payment...' },
  paymentFailed: { ar: 'فشل التحقق من الدفع', en: 'Payment Verification Failed' },
  paymentFailedMsg: { ar: 'عذراً، لم نتمكن من التحقق من دفعتك. يرجى المحاولة لاحقاً.', en: 'Sorry, we couldn\'t verify your payment. Please try again later.' },
  retryPayment: { ar: 'إعادة المحاولة', en: 'Retry' },
  backToHome: { ar: 'العودة للرئيسية', en: 'Back to Home' },
  viewBookings: { ar: 'عرض حجوزاتي', en: 'View My Bookings' },

  // Admin
  adminPanel: { ar: 'لوحة التحكم', en: 'Admin Panel' },
  adminDashboard: { ar: 'نظرة عامة', en: 'Overview' },
  adminCars: { ar: 'إدارة السيارات', en: 'Cars Management' },
  adminBookings: { ar: 'إدارة الحجوزات', en: 'Bookings Management' },
  adminUsers: { ar: 'إدارة المستخدمين', en: 'Users Management' },
  adminTotalUsers: { ar: 'إجمالي المستخدمين', en: 'Total Users' },
  adminTotalCars: { ar: 'إجمالي السيارات', en: 'Total Cars' },
  adminPendingCars: { ar: 'بانتظار الموافقة', en: 'Pending Cars' },
  adminApprovedCars: { ar: 'سيارات معتمدة', en: 'Approved Cars' },
  adminRejectedCars: { ar: 'سيارات مرفوضة', en: 'Rejected Cars' },
  adminTotalBookings: { ar: 'إجمالي الحجوزات', en: 'Total Bookings' },
  adminActiveBookings: { ar: 'حجوزات نشطة', en: 'Active Bookings' },
  adminTotalRevenue: { ar: 'إجمالي الإيرادات', en: 'Total Revenue' },
  adminApprove: { ar: 'موافقة', en: 'Approve' },
  adminReject: { ar: 'رفض', en: 'Reject' },
  adminAllCars: { ar: 'جميع السيارات', en: 'All Cars' },
  backToSite: { ar: 'العودة للموقع', en: 'Back to Site' },
  kwd: { ar: 'د.ك', en: 'KWD' },

  // Messages
  messages: { ar: 'الرسائل', en: 'Messages' },
  noMessages: { ar: 'لا توجد رسائل', en: 'No messages' },
  typeMessage: { ar: 'اكتب رسالتك...', en: 'Type your message...' },
  sendMessage: { ar: 'إرسال', en: 'Send' },
  conversations: { ar: 'المحادثات', en: 'Conversations' },
  unreadMessages: { ar: 'رسائل غير مقروءة', en: 'Unread messages' },
  messagesSent: { ar: 'تم إرسال الرسالة', en: 'Message sent' },
  backToConversations: { ar: 'العودة للمحادثات', en: 'Back to Conversations' },
  selectConversation: { ar: 'اختر محادثة للبدء', en: 'Select a conversation to start' },
  startMessaging: { ar: 'ابدأ محادثة جديدة', en: 'Start a new conversation' },
  loading: { ar: 'جاري التحميل...', en: 'Loading...' },

  // Car detail
  ownerInfo: { ar: 'معلومات المالك', en: 'Owner Information' },
  messageOwner: { ar: 'راسل المالك', en: 'Message Owner' },
  whatsapp: { ar: 'واتساب', en: 'WhatsApp' },
  reviews: { ar: 'التقييمات', en: 'Reviews' },
  user: { ar: 'مستخدم', en: 'User' },
  noReviews: { ar: 'لا توجد تقييمات بعد', en: 'No reviews yet' },

  // Error
  errorTitle: { ar: 'حدث خطأ', en: 'Something went wrong' },
  errorMessage: { ar: 'عذراً، حدث خطأ غير متوقع. يرجى المحاولة مرة أخرى.', en: 'Sorry, an unexpected error occurred. Please try again.' },
  retry: { ar: 'حاول مرة أخرى', en: 'Try Again' },

  // Footer
  copyright: { ar: '© 2025 سكة كار. جميع الحقوق محفوظة.', en: '© 2025 Sikka Car. All rights reserved.' },
  termsOfService: { ar: 'شروط الاستخدام', en: 'Terms of Service' },
  privacyPolicy: { ar: 'سياسة الخصوصية', en: 'Privacy Policy' },
  iUnderstand: { ar: 'فهمت', en: 'I Understand' },
}

interface LanguageContextType {
  lang: Language
  toggleLanguage: () => void
  t: (key: string) => string
  dir: 'rtl' | 'ltr'
}

const LanguageContext = createContext<LanguageContextType | null>(null)

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Language>('ar')

  const toggleLanguage = useCallback(() => {
    setLang((prev) => (prev === 'ar' ? 'en' : 'ar'))
  }, [])

  const t = useCallback(
    (key: string) => {
      return translations[key]?.[lang] || key
    },
    [lang]
  )

  const dir = lang === 'ar' ? 'rtl' : 'ltr'

  return (
    <LanguageContext.Provider value={{ lang, toggleLanguage, t, dir }}>
      <div dir={dir} className={lang === 'ar' ? 'font-arabic' : ''}>
        {children}
      </div>
    </LanguageContext.Provider>
  )
}

export function useLanguage() {
  const context = useContext(LanguageContext)
  if (!context) {
    throw new Error('useLanguage must be used within a LanguageProvider')
  }
  return context
}
