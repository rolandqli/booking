import type { Metadata } from "next";
import "./globals.css";
import ChatWindow from "@/components/ChatWindow";

export const metadata: Metadata = {
  title: "Booking Calendar",
  description: "AI-assisted booking system",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">
        {children}
        <ChatWindow />
      </body>
    </html>
  );
}
