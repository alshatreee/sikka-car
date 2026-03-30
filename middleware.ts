import { clerkMiddleware, createRouteMatcher } from '@clerk/nextjs/server'

const isProtectedRoute = createRouteMatcher([
  '/dashboard(.*)',
  '/list(.*)',
  '/edit(.*)',
  '/admin(.*)',
  '/profile(.*)',
  '/messages(.*)',
  '/contract(.*)',
  '/inspection(.*)',
  '/payment-success(.*)',
])

export default clerkMiddleware((auth, req) => {
  if (isProtectedRoute(req)) {
    auth().protect()
  }
})

export const config = {
  matcher: ['/((?!.*\\..*|_next).*)', '/', '/(api|trpc)(.*)'],
}
