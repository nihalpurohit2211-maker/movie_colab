import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { GoogleOAuthProviderWrapper } from "@/components/GoogleOAuthProviderWrapper";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Drive Ingestion Engine",
  description:
    "Stream any URL directly into Google Drive — zero local storage consumed.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className={inter.className}>
        <GoogleOAuthProviderWrapper>{children}</GoogleOAuthProviderWrapper>
      </body>
    </html>
  );
}
