import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FMES Scanner — AlphaBull",
  description:
    "Daily FMES (Flipping Markets Entry System) setups across Nifty 500, US majors and forex — updated every market close.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <header className="border-b border-white/5">
          <div className="mx-auto max-w-6xl px-4 py-4 flex items-center justify-between">
            <div>
              <h1 className="text-xl font-semibold tracking-tight">
                FMES Scanner
              </h1>
              <p className="text-xs text-foreground/50">
                Live FMES setups · Nifty 500 + US + Forex · Daily
              </p>
            </div>
            <a
              href="https://github.com/ethereum007/fmes-scanner"
              target="_blank"
              rel="noopener"
              className="text-xs text-foreground/50 hover:text-foreground/80"
            >
              github →
            </a>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
        <footer className="mx-auto max-w-6xl px-4 py-8 text-xs text-foreground/40">
          Strategy by Marcell / Flipping Markets · Implementation © AlphaBull
          Academy · Educational use only, not financial advice.
        </footer>
      </body>
    </html>
  );
}
