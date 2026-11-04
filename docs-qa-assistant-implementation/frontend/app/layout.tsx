import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {title:"Solstice Docs Assistant",description:"Grounded answers from authorized Solstice Learning documentation."};
export default function RootLayout({children}:{children:React.ReactNode}) {
  return <html lang="en"><body>{children}</body></html>;
}
