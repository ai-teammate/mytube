/**
 * Regression test for MYTUBE-113: GitHub Pages returned 404 for all routes
 * because actions/configure-pages@v4 ran AFTER the build step. This caused
 * the Pages environment to be set up too late, which could prevent the artifact
 * upload/deployment from succeeding.
 *
 * GitHub's recommended pattern: configure-pages runs BEFORE the build so the
 * Pages environment is validated before any build work is done.
 */

import * as fs from "fs";
import * as path from "path";

describe("deploy-pages.yml workflow configuration", () => {
  let workflowContent: string;

  beforeAll(() => {
    const workflowPath = path.resolve(
      __dirname,
      "../../../../.github/workflows/deploy-pages.yml"
    );
    workflowContent = fs.readFileSync(workflowPath, "utf8");
  });

  it("configure-pages@v4 step must appear before the npm build step", () => {
    const configPagesIdx = workflowContent.indexOf("actions/configure-pages");
    const buildIdx = workflowContent.indexOf("npm run build");

    expect(configPagesIdx).toBeGreaterThan(-1); // configure-pages step is present
    expect(buildIdx).toBeGreaterThan(-1); // build step is present

    // The root cause of MYTUBE-113: configure-pages ran AFTER the build.
    // With this ordering the Pages environment was not validated before uploading,
    // causing the deploy step to fail and leaving the site returning 404.
    expect(configPagesIdx).toBeLessThan(buildIdx);
  });

  it("build step sets GITHUB_PAGES=true so next.config.ts uses basePath /mytube", () => {
    // next.config.ts: basePath = GITHUB_PAGES === 'true' ? '/mytube' : ''
    // Without this env var the exported HTML uses basePath='' and assets
    // are served from / rather than /mytube/, causing 404s on GitHub Pages.
    expect(workflowContent).toContain("GITHUB_PAGES: true");
  });

  it("artifact upload path targets web/out", () => {
    // The Next.js static export writes to web/out. If the path is wrong the
    // uploaded artifact is empty and GitHub Pages returns 404.
    expect(workflowContent).toMatch(/path:\s+['"]?\.\/web\/out['"]?/);
  });

  it("does NOT overwrite public/404.html with the homepage HTML (MYTUBE-280)", () => {
    // Root cause of MYTUBE-280: the workflow used to copy out/index.html over
    // out/404.html.  This caused GitHub Pages to serve pre-rendered *homepage*
    // HTML for every unknown URL (e.g. /v/<uuid>/).  The Next.js App Router
    // then hydrated the DOM as the homepage instead of routing to the watch page.
    //
    // The fix: public/404.html is now a proper SPA redirect page included in
    // the build output by Next.js itself.  The cp step must not be present.
    expect(workflowContent).not.toContain("cp out/index.html out/404.html");
  });
});
