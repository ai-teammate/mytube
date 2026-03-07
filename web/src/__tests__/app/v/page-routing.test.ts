/**
 * Unit test for the routing configuration of src/app/v/[id]/page.tsx.
 *
 * The app uses `output: 'export'` (Next.js static export for GitHub Pages).
 * With static export, `dynamicParams = true` is INCOMPATIBLE and causes the
 * build to fail. The correct configuration is:
 *   - dynamicParams = false  (required for static export)
 *   - generateStaticParams returns a placeholder `[{ id: '_' }]`
 *   - SPA routing for real video UUIDs is handled via public/404.html:
 *     the redirect page stores the UUID in sessionStorage and redirects to
 *     the pre-built shell at /v/_/.  WatchPageClient then reads the real UUID
 *     from sessionStorage (see WatchPageClient-spa.test.tsx for coverage).
 */

// Mock WatchPageClient to isolate the routing config under test.
jest.mock("@/app/v/[id]/WatchPageClient", () => ({
  __esModule: true,
  default: () => null,
}));

import * as PageConfig from "@/app/v/[id]/page";

describe("Watch page routing configuration", () => {
  it("dynamicParams is false — required for Next.js static export (output: export)", () => {
    // dynamicParams = true is incompatible with `output: 'export'` and breaks the build.
    // SPA routing for arbitrary video UUIDs works via the 404.html fallback instead.
    expect(PageConfig.dynamicParams).toBe(false);
  });

  it("generateStaticParams returns a placeholder to create the route shell", () => {
    const params = PageConfig.generateStaticParams();
    expect(params).toEqual([{ id: "_" }]);
  });
});
