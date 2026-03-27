export default function AdminLoading() {
  return (
    <main className="min-h-screen bg-dark-bg px-4 py-8">
      <div className="container">
        {/* Header skeleton */}
        <div className="mb-8">
          <div className="mb-4 h-10 w-48 rounded-lg bg-dark-card animate-pulse" />
          <div className="h-6 w-96 rounded-lg bg-dark-card animate-pulse" />
        </div>

        {/* Overview stats skeleton - 4 columns */}
        <div className="mb-8 grid gap-6 md:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div
              key={i}
              className="rounded-2xl border border-dark-border bg-dark-card p-6 space-y-3"
            >
              {/* Label skeleton */}
              <div className="h-5 w-3/4 rounded-lg bg-dark-surface animate-pulse" />

              {/* Value skeleton */}
              <div className="h-8 w-1/2 rounded-lg bg-status-star/20 animate-pulse" />

              {/* Change indicator skeleton */}
              <div className="h-4 w-2/3 rounded-lg bg-dark-surface animate-pulse" />
            </div>
          ))}
        </div>

        {/* Navigation tabs skeleton */}
        <div className="mb-6 flex flex-wrap gap-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div
              key={i}
              className="h-10 w-40 rounded-lg bg-dark-card animate-pulse"
            />
          ))}
        </div>

        {/* Content area - Table skeleton */}
        <div className="overflow-hidden rounded-2xl border border-dark-border bg-dark-card">
          {/* Header row */}
          <div className="flex gap-4 border-b border-dark-border p-6">
            {Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                className="h-5 flex-1 rounded-lg bg-dark-surface animate-pulse"
              />
            ))}
          </div>

          {/* Data rows */}
          {Array.from({ length: 5 }).map((_, rowI) => (
            <div key={rowI} className="flex gap-4 border-b border-dark-border p-6">
              {Array.from({ length: 6 }).map((_, colI) => (
                <div
                  key={colI}
                  className="h-5 flex-1 rounded-lg bg-dark-surface animate-pulse"
                />
              ))}
            </div>
          ))}
        </div>
      </div>
    </main>
  )
}
