import Link from "next/link";
import { Lato, Libre_Baskerville } from "next/font/google";
import "./globals.css";

const bodyFont = Lato({ subsets: ["latin"], weight: ["400", "700", "900"], variable: "--font-body" });
const headlineFont = Libre_Baskerville({ subsets: ["latin"], weight: ["400", "700"], variable: "--font-headline" });

export const metadata = {
  title: "RealNews | U.S. Congress Vote Tracker",
  description: "Explore U.S. Congress voting records and policy in plain English.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className={bodyFont.variable + " " + headlineFont.variable}>
        <header className="site-header">
          <div className="frame header-inner">
            <Link className="brand" href="/">
              <span className="monogram" aria-hidden="true"><b>R</b>N</span>
              <span>
                <strong>RealNews</strong> <span className="tag">Civic</span>
                <small>U.S. Congress votes in plain English</small>
              </span>
            </Link>
            <nav className="site-nav" aria-label="Main navigation">
              <Link href="/#explore">Explore</Link><Link href="/feed">My feed</Link><Link href="/sign-in">Account</Link>
            </nav>
          </div>
        </header>
        {children}
        <footer className="site-footer" id="about">
          <div className="frame">
            <strong>RealNews</strong>
            <p>A Policy Track project for exploring the U.S. Congress.</p>
          </div>
        </footer>
      </body>
    </html>
  );
}
