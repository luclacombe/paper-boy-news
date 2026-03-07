import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  redirects: async () => {
    const always = [
      {
        source: "/sources",
        destination: "/settings",
        permanent: true,
      },
      {
        source: "/delivery",
        destination: "/settings",
        permanent: true,
      },
      {
        source: "/editions",
        destination: "/dashboard",
        permanent: true,
      },
    ];

    if (process.env.NODE_ENV === "production") {
      return [
        ...always,
        {
          source: "/dev/:path*",
          destination: "/",
          permanent: false,
        },
      ];
    }
    return always;
  },
};

export default nextConfig;
