import CategoryPageClient from "./CategoryPageClient";

export function generateStaticParams() {
  return [];
}

export default function Page(props: { params: Promise<{ id: string }> }) {
  return <CategoryPageClient {...props} />;
}
