/** @type {import('next').NextConfig} */
const nextConfig = {
  async redirects() {
    return [{ source: "/landing", destination: "/", permanent: false }];
  },
};

module.exports = nextConfig;
