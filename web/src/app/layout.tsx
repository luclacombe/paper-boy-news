import type { Metadata } from "next";
import {
  Playfair_Display,
  Libre_Baskerville,
  IM_Fell_English,
  JetBrains_Mono,
  Special_Elite,
} from "next/font/google";
import { Toaster } from "@/components/ui/sonner";
import "./globals.css";

const playfairDisplay = Playfair_Display({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["400", "700", "900"],
  display: "swap",
});

const libreBaskerville = Libre_Baskerville({
  variable: "--font-headline",
  subsets: ["latin"],
  weight: ["400", "700"],
  display: "swap",
});

const imFellEnglish = IM_Fell_English({
  variable: "--font-body",
  subsets: ["latin"],
  weight: ["400"],
  style: ["normal", "italic"],
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  weight: ["400"],
  display: "swap",
});

const specialElite = Special_Elite({
  variable: "--font-typewriter",
  subsets: ["latin"],
  weight: ["400"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Paper Boy News",
  description:
    "Automated morning newspaper for your e-reader. Fetches news from RSS feeds, builds a beautiful EPUB, and delivers it to your Kindle, Kobo, or reMarkable.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${playfairDisplay.variable} ${libreBaskerville.variable} ${imFellEnglish.variable} ${jetbrainsMono.variable} ${specialElite.variable} antialiased`}
      >
        <svg
          style={{ display: "none" }}
          aria-hidden="true"
          xmlns="http://www.w3.org/2000/svg"
        >
          <filter id="inkbleed">
            <feTurbulence
              type="fractalNoise"
              baseFrequency="0.04"
              numOctaves="5"
              seed="2"
              result="noise"
            />
            <feDisplacementMap
              in="SourceGraphic"
              in2="noise"
              scale="1.5"
              xChannelSelector="R"
              yChannelSelector="G"
            />
          </filter>
        </svg>
        {children}
        <Toaster />
      </body>
    </html>
  );
}
