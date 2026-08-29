import type { Metadata } from "next";
import { spaceGrotesk, inter, jetbrainsMono } from "@/lib/fonts";
import { LenisProvider } from "@/lib/lenis-provider";
import "./globals.css";

export const metadata: Metadata = {
  title: "Verity // Autonomous Financial Settlement & Forensic Controller",
  description: "Deterministic settlement reconciliation, non-sycophantic Q&A agent, and cryptographic audit trail.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${spaceGrotesk.variable} ${inter.variable} ${jetbrainsMono.variable} dark`}
    >
      <body className="bg-bg-base text-ink-primary min-h-screen selection:bg-accent-amber/20 selection:text-accent-amber">
        <LenisProvider>{children}</LenisProvider>
      </body>
    </html>
  );
}
