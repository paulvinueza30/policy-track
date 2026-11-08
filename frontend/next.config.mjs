/** @type {import('next').NextConfig} */
const nextConfig = {
  // Google Sign-In needs the page's origin in the referrer on plain http localhost.
  async headers() {
    return [{ source: "/sign-in", headers: [{ key: "Referrer-Policy", value: "no-referrer-when-downgrade" }] }];
  },
};

export default nextConfig;
