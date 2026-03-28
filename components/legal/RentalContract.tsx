'use client'

import { useLanguage } from '@/components/shared/LanguageProvider'

interface RentalContractProps {
  booking: {
    id: string
    startDate: Date
    endDate: Date
    totalDays: number
    totalAmount: string
    notes?: string | null
    car: {
      title: string
      year: number
      category?: string | null
      area: string
      dailyPrice: string
    }
    renter: {
      fullName: string | null
      email: string
      phone?: string | null
    }
  }
  owner: {
    fullName: string | null
    phone?: string | null
  }
}

export function RentalContract({ booking, owner }: RentalContractProps) {
  const { lang } = useLanguage()

  const formatDate = (date: Date) => {
    return new Date(date).toLocaleDateString(
      lang === 'ar' ? 'ar-KW' : 'en-US',
      {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      }
    )
  }

  const formatDateShort = (date: Date) => {
    return new Date(date).toLocaleDateString(
      lang === 'ar' ? 'ar-KW' : 'en-US',
      {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
      }
    )
  }

  const today = new Date()
  const todayFormatted = formatDate(today)

  return (
    <div
      className={`bg-white text-black ${lang === 'ar' ? 'direction-rtl' : ''}`}
      dir={lang === 'ar' ? 'rtl' : 'ltr'}
      style={{ fontSize: '14px', lineHeight: '1.6' }}
    >
      {/* Header */}
      <div style={{ textAlign: 'center', marginBottom: '30px', borderBottom: '2px solid #333', paddingBottom: '20px' }}>
        <h1 style={{ margin: '0 0 10px 0', fontSize: '24px', fontWeight: 'bold' }}>
          {lang === 'ar' ? 'عقد تأجير سيارة' : 'Car Rental Agreement'}
        </h1>
        <p style={{ margin: '0', fontSize: '13px', color: '#666' }}>
          {lang === 'ar' ? 'اتفاقية تأجير رسمية' : 'Official Rental Agreement'}
        </p>
      </div>

      {/* Contract Number & Date */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '20px',
          marginBottom: '25px',
          fontSize: '13px',
        }}
      >
        <div>
          <strong>{lang === 'ar' ? 'رقم العقد' : 'Contract Number'}:</strong>
          <br />
          <span style={{ color: '#666' }}>{booking.id}</span>
        </div>
        <div>
          <strong>{lang === 'ar' ? 'تاريخ الاتفاقية' : 'Agreement Date'}:</strong>
          <br />
          <span style={{ color: '#666' }}>{todayFormatted}</span>
        </div>
      </div>

      {/* Section 1: Owner Info */}
      <div style={{ marginBottom: '25px' }}>
        <h2 style={{ fontSize: '14px', fontWeight: 'bold', marginBottom: '10px', borderBottom: '1px solid #999', paddingBottom: '5px' }}>
          {lang === 'ar' ? 'معلومات مالك السيارة' : 'Car Owner Information'}
        </h2>
        <div style={{ paddingLeft: '20px', paddingRight: '20px' }}>
          <p style={{ margin: '8px 0' }}>
            <strong>{lang === 'ar' ? 'الاسم' : 'Name'}:</strong> {owner.fullName || lang === 'ar' ? 'غير محدد' : 'Not specified'}
          </p>
          <p style={{ margin: '8px 0' }}>
            <strong>{lang === 'ar' ? 'رقم الهاتف' : 'Phone'}:</strong> {owner.phone || lang === 'ar' ? 'غير محدد' : 'Not specified'}
          </p>
        </div>
      </div>

      {/* Section 2: Renter Info */}
      <div style={{ marginBottom: '25px' }}>
        <h2 style={{ fontSize: '14px', fontWeight: 'bold', marginBottom: '10px', borderBottom: '1px solid #999', paddingBottom: '5px' }}>
          {lang === 'ar' ? 'معلومات المستأجر' : 'Renter Information'}
        </h2>
        <div style={{ paddingLeft: '20px', paddingRight: '20px' }}>
          <p style={{ margin: '8px 0' }}>
            <strong>{lang === 'ar' ? 'الاسم' : 'Name'}:</strong> {booking.renter.fullName || booking.renter.email}
          </p>
          <p style={{ margin: '8px 0' }}>
            <strong>{lang === 'ar' ? 'البريد الإلكتروني' : 'Email'}:</strong> {booking.renter.email}
          </p>
          <p style={{ margin: '8px 0' }}>
            <strong>{lang === 'ar' ? 'رقم الهاتف' : 'Phone'}:</strong> {booking.renter.phone || lang === 'ar' ? 'غير محدد' : 'Not specified'}
          </p>
        </div>
      </div>

      {/* Section 3: Car Info */}
      <div style={{ marginBottom: '25px' }}>
        <h2 style={{ fontSize: '14px', fontWeight: 'bold', marginBottom: '10px', borderBottom: '1px solid #999', paddingBottom: '5px' }}>
          {lang === 'ar' ? 'معلومات السيارة' : 'Car Information'}
        </h2>
        <div style={{ paddingLeft: '20px', paddingRight: '20px' }}>
          <p style={{ margin: '8px 0' }}>
            <strong>{lang === 'ar' ? 'الطراز' : 'Model/Title'}:</strong> {booking.car.title}
          </p>
          <p style={{ margin: '8px 0' }}>
            <strong>{lang === 'ar' ? 'السنة' : 'Year'}:</strong> {booking.car.year}
          </p>
          {booking.car.category && (
            <p style={{ margin: '8px 0' }}>
              <strong>{lang === 'ar' ? 'الفئة' : 'Category'}:</strong> {booking.car.category}
            </p>
          )}
          <p style={{ margin: '8px 0' }}>
            <strong>{lang === 'ar' ? 'المنطقة' : 'Area'}:</strong> {booking.car.area}
          </p>
        </div>
      </div>

      {/* Section 4: Rental Period */}
      <div style={{ marginBottom: '25px' }}>
        <h2 style={{ fontSize: '14px', fontWeight: 'bold', marginBottom: '10px', borderBottom: '1px solid #999', paddingBottom: '5px' }}>
          {lang === 'ar' ? 'فترة الإيجار' : 'Rental Period'}
        </h2>
        <div style={{ paddingLeft: '20px', paddingRight: '20px' }}>
          <p style={{ margin: '8px 0' }}>
            <strong>{lang === 'ar' ? 'تاريخ البداية' : 'Start Date'}:</strong> {formatDate(booking.startDate)}
          </p>
          <p style={{ margin: '8px 0' }}>
            <strong>{lang === 'ar' ? 'تاريخ النهاية' : 'End Date'}:</strong> {formatDate(booking.endDate)}
          </p>
          <p style={{ margin: '8px 0' }}>
            <strong>{lang === 'ar' ? 'عدد الأيام' : 'Total Days'}:</strong> {booking.totalDays} {lang === 'ar' ? 'يوم' : 'day(s)'}
          </p>
        </div>
      </div>

      {/* Section 5: Financial Terms */}
      <div style={{ marginBottom: '25px', backgroundColor: '#f9f9f9', padding: '15px', borderRadius: '5px' }}>
        <h2 style={{ fontSize: '14px', fontWeight: 'bold', marginBottom: '10px' }}>
          {lang === 'ar' ? 'الشروط المالية' : 'Financial Terms'}
        </h2>
        <div style={{ paddingLeft: '20px', paddingRight: '20px' }}>
          <p style={{ margin: '8px 0' }}>
            <strong>{lang === 'ar' ? 'السعر اليومي' : 'Daily Price'}:</strong> {booking.car.dailyPrice} {lang === 'ar' ? 'د.ك' : 'KWD'}
          </p>
          <p style={{ margin: '8px 0' }}>
            <strong>{lang === 'ar' ? 'عدد الأيام' : 'Number of Days'}:</strong> {booking.totalDays}
          </p>
          <p
            style={{
              margin: '12px 0 8px 0',
              fontSize: '16px',
              fontWeight: 'bold',
              borderTop: '1px solid #ccc',
              paddingTop: '10px',
            }}
          >
            <strong>{lang === 'ar' ? 'المبلغ الإجمالي' : 'Total Amount'}:</strong> {booking.totalAmount} {lang === 'ar' ? 'د.ك' : 'KWD'}
          </p>
        </div>
      </div>

      {/* Section 6: Terms and Conditions */}
      <div style={{ marginBottom: '25px' }}>
        <h2 style={{ fontSize: '14px', fontWeight: 'bold', marginBottom: '10px', borderBottom: '1px solid #999', paddingBottom: '5px' }}>
          {lang === 'ar' ? 'الشروط والأحكام' : 'Terms and Conditions'}
        </h2>
        <div style={{ paddingLeft: '20px', paddingRight: '20px' }}>
          {lang === 'ar' ? (
            <ol style={{ margin: '0', paddingLeft: '20px', direction: 'rtl' }}>
              <li style={{ margin: '10px 0' }}>
                <strong>مسؤولية المستأجر:</strong> المستأجر مسؤول عن السيارة خلال فترة الإيجار بالكامل.
              </li>
              <li style={{ margin: '10px 0' }}>
                <strong>حالة السيارة:</strong> يجب إرجاع السيارة بنفس الحالة التي استلمها المستأجر. أي أضرار أو تلفيات يتحملها المستأجر.
              </li>
              <li style={{ margin: '10px 0' }}>
                <strong>المسؤولية عن الأضرار:</strong> أي ضرر يحدث للسيارة أثناء فترة الإيجار يتحمله المستأجر.
              </li>
              <li style={{ margin: '10px 0' }}>
                <strong>التأخير في الإرجاع:</strong> التأخير في إرجاع السيارة يحسب كيوم إيجار كامل إضافي.
              </li>
              <li style={{ margin: '10px 0' }}>
                <strong>تأجير السيارة لطرف ثالث:</strong> ممنوع تأجير السيارة لطرف ثالث أو السماح لشخص آخر بقيادتها.
              </li>
              <li style={{ margin: '10px 0' }}>
                <strong>السفر خارج الكويت:</strong> ممنوع السفر خارج الكويت بدون موافقة كتابية من مالك السيارة.
              </li>
              <li style={{ margin: '10px 0' }}>
                <strong>المخالفات المرورية:</strong> المستأجر يتحمل جميع المخالفات المرورية التي تحدث خلال فترة الإيجار.
              </li>
            </ol>
          ) : (
            <ol style={{ margin: '0', paddingLeft: '20px' }}>
              <li style={{ margin: '10px 0' }}>
                <strong>Renter Responsibility:</strong> The renter is fully responsible for the vehicle during the entire rental period.
              </li>
              <li style={{ margin: '10px 0' }}>
                <strong>Vehicle Condition:</strong> The vehicle must be returned in the same condition as received. Any damage or wear is the renter's responsibility.
              </li>
              <li style={{ margin: '10px 0' }}>
                <strong>Damage Liability:</strong> Any damage to the vehicle during the rental period is the renter's responsibility.
              </li>
              <li style={{ margin: '10px 0' }}>
                <strong>Late Return:</strong> Late return of the vehicle will be charged as a full additional day's rental.
              </li>
              <li style={{ margin: '10px 0' }}>
                <strong>Third Party Subletting:</strong> Renting the vehicle to a third party or allowing someone else to drive is prohibited.
              </li>
              <li style={{ margin: '10px 0' }}>
                <strong>Travel Outside Kuwait:</strong> Travel outside Kuwait is prohibited without written permission from the owner.
              </li>
              <li style={{ margin: '10px 0' }}>
                <strong>Traffic Violations:</strong> The renter bears responsibility for all traffic violations during the rental period.
              </li>
            </ol>
          )}
        </div>
      </div>

      {/* Additional Notes */}
      {booking.notes && (
        <div style={{ marginBottom: '25px' }}>
          <h2 style={{ fontSize: '14px', fontWeight: 'bold', marginBottom: '10px', borderBottom: '1px solid #999', paddingBottom: '5px' }}>
            {lang === 'ar' ? 'ملاحظات إضافية' : 'Additional Notes'}
          </h2>
          <div style={{ paddingLeft: '20px', paddingRight: '20px', color: '#666' }}>
            {booking.notes}
          </div>
        </div>
      )}

      {/* Signatures Section */}
      <div style={{ marginTop: '40px', paddingTop: '20px', borderTop: '2px solid #333' }}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: '40px',
            textAlign: 'center',
          }}
        >
          {/* Renter Signature */}
          <div style={{ textAlign: lang === 'ar' ? 'right' : 'left' }}>
            <p style={{ margin: '0 0 40px 0', fontSize: '12px', color: '#666' }}>
              {lang === 'ar' ? 'التاريخ / Date: ________' : 'Date: ________'}
            </p>
            <div style={{ borderTop: '1px solid #333', paddingTop: '5px' }}>
              <p style={{ margin: '8px 0 0 0', fontSize: '12px' }}>
                {lang === 'ar' ? 'توقيع المستأجر / Renter Signature' : 'Renter Signature'}
              </p>
              <p style={{ margin: '4px 0 0 0', fontSize: '11px', color: '#666' }}>
                {booking.renter.fullName || booking.renter.email}
              </p>
            </div>
          </div>

          {/* Owner Signature */}
          <div style={{ textAlign: lang === 'ar' ? 'left' : 'right' }}>
            <p style={{ margin: '0 0 40px 0', fontSize: '12px', color: '#666' }}>
              {lang === 'ar' ? 'التاريخ / Date: ________' : 'Date: ________'}
            </p>
            <div style={{ borderTop: '1px solid #333', paddingTop: '5px' }}>
              <p style={{ margin: '8px 0 0 0', fontSize: '12px' }}>
                {lang === 'ar' ? 'توقيع مالك السيارة / Owner Signature' : 'Owner Signature'}
              </p>
              <p style={{ margin: '4px 0 0 0', fontSize: '11px', color: '#666' }}>
                {owner.fullName || lang === 'ar' ? 'غير محدد' : 'Not specified'}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div
        style={{
          marginTop: '40px',
          paddingTop: '20px',
          borderTop: '1px solid #ddd',
          textAlign: 'center',
          fontSize: '11px',
          color: '#999',
        }}
      >
        <p style={{ margin: '0' }}>
          {lang === 'ar'
            ? 'هذا العقد تم توليده بواسطة منصة سكة كار للتأجير'
            : 'This contract was generated by Sikka Car Rental Platform'}
        </p>
        <p style={{ margin: '4px 0 0 0' }}>
          {lang === 'ar'
            ? 'يرجى الاحتفاظ بنسخة من هذا العقد لسجلاتك'
            : 'Please keep a copy of this contract for your records'}
        </p>
      </div>
    </div>
  )
}
