import { ImageResponse } from 'next/og'

export const runtime = 'edge'
export const alt = 'Sikka Car - سكة كار'
export const size = { width: 1200, height: 630 }
export const contentType = 'image/png'

export default async function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: '#111111',
          padding: '40px',
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        {/* Decorative gold line - top */}
        <div
          style={{
            position: 'absolute',
            top: '60px',
            left: '80px',
            right: '80px',
            height: '3px',
            backgroundColor: '#FFB800',
          }}
        />

        {/* Main content container */}
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '20px',
            zIndex: 1,
          }}
        >
          {/* English title - Sikka Car */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '20px',
              fontSize: '80px',
              fontWeight: 'bold',
              letterSpacing: '-2px',
            }}
          >
            <span style={{ color: '#FFFFFF' }}>Sikka</span>
            <span style={{ color: '#FFB800' }}>Car</span>
          </div>

          {/* Arabic title - سكة كار */}
          <div
            style={{
              fontSize: '56px',
              fontWeight: '600',
              color: '#FFFFFF',
              textAlign: 'center',
              direction: 'rtl',
              marginTop: '10px',
            }}
          >
            سكة كار
          </div>

          {/* Decorative gold line - middle */}
          <div
            style={{
              width: '200px',
              height: '2px',
              backgroundColor: '#FFB800',
              margin: '20px 0',
            }}
          />

          {/* Tagline - Arabic */}
          <div
            style={{
              fontSize: '32px',
              color: '#AAAAAA',
              textAlign: 'center',
              direction: 'rtl',
              marginTop: '10px',
              fontWeight: '400',
            }}
          >
            منصة تأجير السيارات في الكويت
          </div>
        </div>

        {/* Decorative gold line - bottom */}
        <div
          style={{
            position: 'absolute',
            bottom: '60px',
            left: '80px',
            right: '80px',
            height: '3px',
            backgroundColor: '#FFB800',
          }}
        />
      </div>
    ),
    {
      ...size,
    }
  )
}
