export const uploadToCloudinary = async (
  file: File,
  uploadPreset = 'sikka_cars_documents'
) => {
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
