import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { dark } from "@clerk/themes";
import { IBM_Plex_Mono, Space_Grotesk } from "next/font/google";
import "./globals.css";

const spaceGrotesk = Space_Grotesk({
  variable: "--font-space-grotesk",
  subsets: ["latin"],
  display: "swap",
});

const ibmPlexMono = IBM_Plex_Mono({
  variable: "--font-ibm-plex-mono",
  weight: ["400", "500", "600"],
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "AutoAI · Control Room",
  description:
    "Mission control for autonomous vehicle lifecycle orchestration — real-time telemetry, diagnostics, and predictive maintenance.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${spaceGrotesk.variable} ${ibmPlexMono.variable}`} suppressHydrationWarning>
      <body>
        <ClerkProvider
          appearance={{
            baseTheme: dark,
            variables: {
              colorBackground: "#1e293b",
              colorPrimary: "#818cf8",
              colorText: "#ffffff",
              colorTextSecondary: "#cbd5e1",
              colorInputBackground: "#0f172a",
              colorInputText: "#ffffff",
              borderRadius: "12px",
            },
          }}
        >
          {children}
        </ClerkProvider>
      </body>
    </html>
  );
}
