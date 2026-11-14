import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Image autonome pour Cloud Run (voir apps/web/Dockerfile).
  output: "standalone",
  poweredByHeader: false,
  reactStrictMode: true,
};

export default nextConfig;
