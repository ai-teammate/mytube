/**
 * Tests that web/src/app/category/[id]/page.tsx is correctly configured
 * for Next.js static export (output: 'export').
 *
 * Bug MYTUBE-186: export const revalidate = 0 marks the route as dynamically
 * rendered, which is incompatible with output: 'export'. This causes the
 * client-side router to exclude the route from its manifest so that the SPA
 * 404.html fallback never navigates to /category/[id] — the home page renders
 * instead.
 */

// Mock the client component so the import of page.tsx does not pull in
// JSX / browser APIs that are unavailable in the Jest node environment.
jest.mock("@/app/category/[id]/CategoryPageClient", () => ({
  __esModule: true,
  default: () => null,
}));

describe("Category page static-export configuration", () => {
  it("must NOT export revalidate = 0 (incompatible with output: export)", async () => {
    // revalidate = 0 signals dynamic rendering which breaks static export
    // routing: the route is excluded from the client-side router manifest and
    // the SPA shell cannot navigate to /category/[id].
    // After the fix this export is removed, so mod.revalidate is undefined.
    const mod = await import("@/app/category/[id]/page");
    expect(mod.revalidate).not.toBe(0);
  });

  it("generateStaticParams must return an array (static export contract)", async () => {
    const mod = await import("@/app/category/[id]/page");
    const result = mod.generateStaticParams();
    expect(Array.isArray(result)).toBe(true);
  });
});
