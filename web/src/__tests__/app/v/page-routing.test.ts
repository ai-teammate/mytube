/**
 * Unit test for the routing configuration of src/app/v/[id]/page.tsx.
 *
 * Reproduces bug MYTUBE-225: dynamicParams = false prevents the Next.js
 * client-side router from rendering the watch page for real video IDs
 * (anything other than the '_' placeholder in generateStaticParams).
 * When dynamicParams is false, navigating to /v/<uuid> via the SPA 404
 * fallback returns a 404 within the app instead of rendering the player.
 */

// Mock WatchPageClient to isolate the routing config under test.
jest.mock("@/app/v/[id]/WatchPageClient", () => ({
  __esModule: true,
  default: () => null,
}));

import * as PageConfig from "@/app/v/[id]/page";

describe("Watch page routing configuration", () => {
  it("dynamicParams is not false — watch page must render for arbitrary video IDs via SPA fallback", () => {
    // dynamicParams = false causes the Next.js router to 404 for any ID not
    // returned by generateStaticParams(). Since only '_' is pre-generated,
    // all real video UUIDs would return 404 and the player never initialises.
    // The value must be true (or undefined/not exported, which defaults to true).
    expect(PageConfig.dynamicParams).not.toBe(false);
  });

  it("generateStaticParams returns a placeholder to create the route shell", () => {
    const params = PageConfig.generateStaticParams();
    expect(params).toEqual([{ id: "_" }]);
  });
});
