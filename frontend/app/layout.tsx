import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CampusRAG",
  description: "University knowledge retrieval and question-answering platform.",
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
