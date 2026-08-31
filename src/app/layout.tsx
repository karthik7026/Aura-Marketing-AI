import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Aura Marketing AI OS & AI Studio",
  description: "AI-Powered Digital Marketing Operating System",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased dark">
      <body className="min-h-full flex flex-col bg-[#030712] text-slate-100 font-sans">{children}</body>
    </html>
  );
}
