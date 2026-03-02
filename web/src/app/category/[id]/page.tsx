import CategoryPageClient from "./CategoryPageClient";

// revalidate = 0 opts this route out of the static export
// pre-render check. All rendering is client-side via the SPA
// shell (404.html); Next.js routing still works client-side.
export const revalidate = 0;

export function generateStaticParams() {
  return [];
}

export default function Page(props: { params: Promise<{ id: string }> }) {
  return <CategoryPageClient {...props} />;
}
