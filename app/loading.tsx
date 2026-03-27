export default function Loading() {
  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <div className="flex flex-col items-center gap-6">
        <div className="h-16 w-16 rounded-full border-4 border-dark-border border-t-status-star animate-spin" />
        <p className="text-text-secondary">جاري التحميل...</p>
      </div>
    </main>
  )
}
