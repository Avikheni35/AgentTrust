/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: false,
  output: "standalone",
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.NEXT_INTERNAL_API_URL || "http://backend:8000"}/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
