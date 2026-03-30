import { withSentryConfig } from '@sentry/nextjs'

/** @type {import('next').NextConfig} */
const nextConfig = {
    images: {
          remotePatterns: [
            {
                      protocol: 'https',
                      hostname: 'res.cloudinary.com',
            },
            {
                      protocol: 'https',
                      hostname: 'picsum.photos',
            },
            {
                      protocol: 'https',
                      hostname: 'img.clerk.com',
            },
                ],
    },
}

export default withSentryConfig(nextConfig, {
    // Sentry org and project from environment variables
                                  org: process.env.SENTRY_ORG,
    project: process.env.SENTRY_PROJECT,

    // Only print logs for uploading source maps in CI
    silent: !process.env.CI,

    // Upload larger set of source maps for prettier stack traces
    widenClientFileUpload: true,

    // Automatically tree-shake Sentry logger statements to reduce bundle size
    disableLogger: true,

    // Hides source maps from generated client bundles
    hideSourceMaps: true,
})
