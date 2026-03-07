import CategoryPageClient from "./CategoryPageClient";

export const dynamic = "force-static";
export const dynamicParams = false;

export function generateStaticParams() {
  // Return a placeholder so Next.js generates a static shell for this route.
  // Real category IDs are handled client-side via the 404.html SPA fallback.
  return [{ id: '_' }];
}

export default function Page(props: { params: Promise<{ id: string }> }) {
  return <CategoryPageClient {...props} />;
}
