/** @type {import('next').NextConfig} */
const isProd = process.env.NODE_ENV === 'production';
const devApiProxyTarget = process.env.DEV_API_PROXY_TARGET || 'http://127.0.0.1:8000';

const nextConfig = {
  trailingSlash: true,
  images: {
    unoptimized: true,
  },
  ...(isProd
    ? { output: 'export' }
    : {
        allowedDevOrigins: ['127.0.0.1'],
        async rewrites() {
          return [
            {
              source: '/backend/:path*',
              destination: `${devApiProxyTarget}/:path*`,
            },
          ];
        },
      }),
  basePath: isProd ? '/scoutdash' : '',
  assetPrefix: isProd ? '/scoutdash/' : '',
};

export default nextConfig;
