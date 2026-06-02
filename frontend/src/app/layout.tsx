import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Argus — multi-agent deep-research engine",
  description:
    "A framework-free, horizontally-autoscaled multi-agent deep-research engine: plan, parallel search over the live web and a local contextual-RAG corpus, synthesize, and reflect.",
  keywords: ["agents", "deep research", "RAG", "multi-agent", "LLM"],
  openGraph: {
    title: "Argus — multi-agent deep-research engine",
    description:
      "Framework-free agentic research over the live web and a local contextual-RAG corpus.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
