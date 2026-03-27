export default function CarDetailLoading() {
  return (
    <main className="min-h-screen bg-dark-bg px-4 py-8">
      <div className="container">
        {/* Back button skeleton */}
        <div className="mb-6 h-10 w-24 rounded-lg bg-dark-card animate-pulse" />

        <div className="grid gap-8 lg:grid-cols-3">
          {/* Image section */}
          <div className="lg:col-span-2">
            {/* Main image skeleton */}
            <div className="mb-4 aspect-video w-full rounded-2xl border border-dark-border bg-dark-card animate-pulse" />

            {/* Thumbnail grid skeleton */}
            <div className="grid grid-cols-4 gap-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <div
                  key={i}
                  className="aspect-square rounded-lg border border-dark-border bg-dark-card animate-pulse"
                />
              ))}
            </div>
          </div>

          {/* Details section */}
          <div className="rounded-2xl border border-dark-border bg-dark-card p-6 space-y-6 h-fit">
            {/* Title skeleton */}
            <div className="space-y-2">
              <div className="h-8 w-3/4 rounded-lg bg-dark-surface animate-pulse" />
              <div className="h-6 w-1/2 rounded-lg bg-dark-surface animate-pulse" />
            </div>

            {/* Price skeleton */}
            <div className="space-y-2 py-6 border-y border-dark-border">
              <div className="h-10 w-1/2 rounded-lg bg-status-star/20 animate-pulse" />
              <div className="h-4 w-1/3 rounded-lg bg-dark-surface animate-pulse" />
            </div>

            {/* Features skeleton */}
            <div className="space-y-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="flex justify-between">
                  <div className="h-4 w-20 rounded-lg bg-dark-surface animate-pulse" />
                  <div className="h-4 w-24 rounded-lg bg-dark-surface animate-pulse" />
                </div>
              ))}
            </div>

            {/* Buttons skeleton */}
            <div className="flex gap-3 pt-4">
              <div className="flex-1 h-12 rounded-xl bg-dark-surface animate-pulse" />
              <div className="flex-1 h-12 rounded-xl bg-dark-surface animate-pulse" />
            </div>
          </div>
        </div>

        {/* Description section */}
        <div className="mt-8 rounded-2xl border border-dark-border bg-dark-card p-6">
          <div className="mb-4 h-8 w-32 rounded-lg bg-dark-surface animate-pulse" />
          <div className="space-y-2">
            {Array.from({ length: 3 }).map((_, i) => (
              <div
                key={i}
                className="h-4 rounded-lg bg-dark-surface animate-pulse"
              />
            ))}
          </div>
        </div>
      </div>
    </main>
  )
}
