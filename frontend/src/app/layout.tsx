import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Agent WAF Dashboard",
  description: "Live policy decisions and protected tool activity.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
