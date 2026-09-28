/** @type {import('next').NextConfig} */
const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || process.env.BACKEND_URL || 'http://127.0.0.1:8000';

const isStaticExport = process.env.STATIC_EXPORT === 'true';

const nextConfig = {
  reactStrictMode: true,
  ...(isStaticExport ? { output: 'export' } : {}),
  images: {
    unoptimized: true,
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '**',
      },
    ],
  },
  // Reverse proxy sang FastAPI Backend giup Cloudflare Tunnel va Vercel phan hoi tuc thi
  ...(!isStaticExport ? {
    async rewrites() {
      const target = backendUrl.replace(/\/$/, '');
      const cleanTarget = target.endsWith('/api/v1') ? target : `${target}/api/v1`;
      return [
        {
          source: '/api/v1/:path*',
          destination: `${cleanTarget}/:path*`,
        },
      ];
    },
  } : {}),
};

export default nextConfig;
