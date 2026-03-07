/**
 * SiteFooter renders the global site footer with placeholder links for
 * Terms of Service and Privacy Policy, plus a copyright notice.
 */
export default function SiteFooter() {
  const year = new Date().getFullYear();

  return (
    <footer className="bg-white border-t border-gray-200 px-4 py-6 mt-auto">
      <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
        <p className="text-sm text-gray-500">
          &copy; {year} mytube. All rights reserved.
        </p>
        <nav aria-label="Footer navigation" className="flex items-center gap-6">
          <a
            href="/terms"
            className="text-sm text-gray-500 hover:text-gray-700 transition-colors"
          >
            Terms
          </a>
          <a
            href="/privacy"
            className="text-sm text-gray-500 hover:text-gray-700 transition-colors"
          >
            Privacy
          </a>
        </nav>
      </div>
    </footer>
  );
}
