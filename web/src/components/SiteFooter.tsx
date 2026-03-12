import Link from "next/link";

/**
 * SiteFooter renders the global site footer with copyright notice and footer links.
 * Uses design tokens: --bg-card background, --border-light top border, --text-subtle text.
 */
export default function SiteFooter() {
  const year = new Date().getFullYear();

  return (
    <footer
      style={{
        background: "var(--bg-card)",
        borderTop: "1px solid var(--border-light)",
      }}
      className="px-10 py-6 mt-auto"
    >
      <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
        <p
          className="text-[13px]"
          style={{ color: "var(--text-subtle)" }}
        >
          &copy; {year} mytube. All rights reserved.
        </p>
        <nav aria-label="Footer navigation" className="flex items-center gap-6">
          <Link
            href="/terms"
            className="text-[13px] transition-colors hover:opacity-80"
            style={{ color: "var(--text-subtle)" }}
          >
            Terms
          </Link>
          <Link
            href="/privacy"
            className="text-[13px] transition-colors hover:opacity-80"
            style={{ color: "var(--text-subtle)" }}
          >
            Privacy
          </Link>
        </nav>
      </div>
    </footer>
  );
}
