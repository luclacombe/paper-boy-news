import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  headers: async () => [
    {
      source: "/:path*",
      headers: [
        { key: "X-Frame-Options", value: "DENY" },
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        {
          key: "Strict-Transport-Security",
          value: "max-age=31536000; includeSubDomains",
        },
        {
          key: "Permissions-Policy",
          value: "camera=(), microphone=(), geolocation=()",
        },
      ],
    },
  ],
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
