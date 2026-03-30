const MAX_FILE_SIZE = 10 * 1024 * 1024 // 10MB
const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif']
const ALLOWED_PRESETS = [
  'sikka_cars_documents',
  'sikka_cars_images',
  'sikka_id_docs',
  'sikka_booking_photos',
]

export const uploadToCloudinary = async (
  file: File,
  uploadPreset = 'sikka_cars_documents'
) => {
  // Validate file size
  if (file.size > MAX_FILE_SIZE) {
    throw new Error('حجم الصورة يجب أن يكون أقل من 10 ميجابايت')
  }

  // Validate file type
  if (!ALLOWED_TYPES.includes(file.type)) {
    throw new Error('نوع الملف غير مدعوم. يرجى رفع صورة (JPEG, PNG, WebP)')
  }

  // Validate upload preset
  if (!ALLOWED_PRESETS.includes(uploadPreset)) {
    throw new Error('Invalid upload preset')
  }

  const formData = new FormData()
  formData.append('file', file)
  formData.append('upload_preset', uploadPreset)

  const cloudName = process.env.NEXT_PUBLIC_CLOUDINARY_CLOUD_NAME
  if (!cloudName) throw new Error('NEXT_PUBLIC_CLOUDINARY_CLOUD_NAME is missing')

  try {
    const res = await fetch(
      `https://api.cloudinary.com/v1_1/${cloudName}/image/upload`,
      {
        method: 'POST',
        body: formData,
      }
    )

    if (!res.ok) {
      throw new Error('فشل رفع الصورة إلى Cloudinary')
    }

    const data = await res.json()
    return data.secure_url as string
  } catch (error) {
    console.error('Cloudinary upload failed:', error)
    return null
  }
}
