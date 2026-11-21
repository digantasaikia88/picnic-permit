import type { NextConfig } from "next";

// Development only. The browser always calls relative /api/... URLs.
// In development Next.js forwards them to the backend container;
// in production Nginx does, so no rewrite is built into the image.
const backendInternalUrl = process.env.BACKEND_INTERNAL_URL;

// Development only. File change events do not cross a Windows bind mount
// into the container, so the dev server polls for changes instead.
const watchPollMs = Number(process.env.NEXT_WATCH_POLL_MS ?? 0);

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  ...(watchPollMs > 0 ? { watchOptions: { pollIntervalMs: watchPollMs } } : {}),
  async rewrites() {
    if (!backendInternalUrl) return [];
    return [
      {
        source: "/api/:path*",
        destination: `${backendInternalUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
