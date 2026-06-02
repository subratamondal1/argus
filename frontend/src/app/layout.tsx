import type { Metadata } from "next";
import { Inter, JetBrains_Mono, Source_Serif_4 } from "next/font/google";

import "./globals.css";

const sans = Inter({ variable: "--font-inter", subsets: ["latin"] });
const serif = Source_Serif_4({ variable: "--font-source-serif", subsets: ["latin"] });
const mono = JetBrains_Mono({ variable: "--font-jetbrains", subsets: ["latin"] });

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
      className={`${sans.variable} ${serif.variable} ${mono.variable} h-full antialiased`}
    >
      <body className="min-h-full">{children}</body>
    </html>
  );
}
