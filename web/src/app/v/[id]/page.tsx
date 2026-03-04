import WatchPageClient from "./WatchPageClient";

export const dynamic = "force-static";

// dynamicParams = true (default): the client-side router renders this page for
// any video ID. The 404.html SPA fallback in deploy-pages.yml serves the app
// shell for paths not pre-generated, and the router then renders the watch page
// with the real ID extracted from the URL.
export const dynamicParams = true;

export function generateStaticParams() {
  // Return a placeholder so Next.js generates a static shell for this route.
  // Real video IDs are handled client-side via the 404.html SPA fallback.
  return [{ id: '_' }];
}

export default function Page(props: { params: Promise<{ id: string }> }) {
  return <WatchPageClient {...props} />;
}
