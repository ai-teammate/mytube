import type { NextConfig } from "next";

const basePath = process.env.GITHUB_PAGES === "true" ? "/mytube" : "";

const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  basePath,
  assetPrefix: basePath,
  env: {
    NEXT_PUBLIC_BASE_PATH: basePath,
  },
  images: {
    remotePatterns: [
      // Google profile photos (Firebase/Google Sign-in avatar_url)
      { protocol: "https", hostname: "lh3.googleusercontent.com" },
      // GCS thumbnails stored via Cloud Storage
      { protocol: "https", hostname: "storage.googleapis.com" },
    ],
    // Required for static export — disables Next.js image optimisation pipeline.
    unoptimized: true,
  },
};

export default nextConfig;
