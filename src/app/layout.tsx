import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ESM — Spatial Awareness System",
  description: "Assistive spatial awareness, real-time sensing, forward computer vision, and environmental mapping.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
