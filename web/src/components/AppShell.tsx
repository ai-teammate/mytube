"use client";

import { usePathname } from "next/navigation";
import { ReactNode } from "react";
import SiteHeader from "@/components/SiteHeader";
import SiteFooter from "@/components/SiteFooter";
import DecorPlay from "@/components/icons/DecorPlay";
import DecorFilm from "@/components/icons/DecorFilm";
import DecorCamera from "@/components/icons/DecorCamera";
import DecorWave from "@/components/icons/DecorWave";

/** Routes that use a minimal layout without the global header/footer. */
const AUTH_ROUTES = ["/login", "/register"];

interface AppShellProps {
  children: ReactNode;
}

/**
 * AppShell wraps every page with a full-viewport page-wrap that carries
 * four decorative SVG background elements, and an inner shell container
 * with rounded corners and a shadow.
 *
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
    <div className="page-wrap">
      {/* Decorative background icons — outside shell, z-index 1 */}
      <DecorPlay className="decor play" />
      <DecorFilm className="decor film" />
      <DecorCamera className="decor camera" />
      <DecorWave className="decor wave" />

      {/* Main shell container */}
      <div className="shell">
        <SiteHeader />
        <main className="flex-1">{children}</main>
        <SiteFooter />
      </div>
    </div>
  );
}
