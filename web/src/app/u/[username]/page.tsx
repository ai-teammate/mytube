import UserProfilePageClient from "./UserProfilePageClient";

export const dynamic = "force-static";
export const dynamicParams = false;

export function generateStaticParams() {
  // Return a placeholder so Next.js generates a static shell for this route.
  // Real usernames are handled client-side via the 404.html SPA fallback.
  return [{ username: '_' }];
}

export default function Page(props: { params: Promise<{ username: string }> }) {
  return <UserProfilePageClient {...props} />;
}
