export default function BrowseLoading() {
  return (
    <main className="min-h-screen bg-dark-bg px-4 py-8">
      <div className="container">
        {/* Header skeleton */}
        <div className="mb-8">
          <div className="mb-4 h-10 w-48 rounded-lg bg-dark-card animate-pulse" />
          <div className="h-6 w-96 rounded-lg bg-dark-card animate-pulse" />
        </div>

        {/* Filters skeleton */}
        <div className="mb-8 flex flex-col gap-4 lg:flex-row">
          <div className="flex-1 h-12 rounded-xl bg-dark-card animate-pulse" />
          <div className="h-12 w-32 rounded-xl bg-dark-card animate-pulse" />
          <div className="h-12 w-32 rounded-xl bg-dark-card animate-pulse" />
        </div>

        {/* Grid of car card skeletons - 3 columns */}
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="overflow-hidden rounded-2xl border border-dark-border bg-dark-card"
            >
              {/* Image skeleton */}
              <div className="aspect-video w-full bg-dark-surface animate-pulse" />

              {/* Content skeleton */}
              <div className="p-4 space-y-3">
                {/* Car name */}
                <div className="h-6 w-3/4 rounded-lg bg-dark-surface animate-pulse" />

                {/* Details */}
                <div className="space-y-2">
                  <div className="h-4 w-1/2 rounded-lg bg-dark-surface animate-pulse" />
                  <div className="h-4 w-2/3 rounded-lg bg-dark-surface animate-pulse" />
                </div>

                {/* Price skeleton */}
                <div className="flex justify-between pt-2">
                  <div className="h-6 w-20 rounded-lg bg-status-star/20 animate-pulse" />
                  <div className="h-6 w-20 rounded-lg bg-dark-surface animate-pulse" />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </main>
  )
}
