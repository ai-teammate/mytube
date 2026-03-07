"use client";

import { usePathname } from "next/navigation";
import { ReactNode } from "react";
import SiteHeader from "@/components/SiteHeader";
import SiteFooter from "@/components/SiteFooter";

/** Routes that use a minimal layout without the global header/footer. */
const AUTH_ROUTES = ["/login", "/register"];

interface AppShellProps {
  children: ReactNode;
}

/**
 * AppShell wraps every page with a consistent header and footer.
 * Auth pages (/login, /register) are rendered without the shell so they
 * present a clean, focused credential-entry experience.
 */
export default function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  const isAuthRoute = AUTH_ROUTES.includes(pathname);

  if (isAuthRoute) {
    return <>{children}</>;
  }

  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      <SiteHeader />
      <main className="flex-1">{children}</main>
      <SiteFooter />
    </div>
  );
}
