import type { NextConfig } from "next";

// Standalone output is only used inside the Docker build (Linux). Skipping it
// on Windows avoids EPERM errors caused by OneDrive blocking symlinks.
const nextConfig: NextConfig = {
  reactStrictMode: true,
  ...(process.env.NEXT_OUTPUT_STANDALONE === "true"
    ? { output: "standalone" as const }
    : {}),
};

export default nextConfig;
