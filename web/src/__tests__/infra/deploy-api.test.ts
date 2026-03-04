/**
 * Regression test for MYTUBE-225: Video.js player never initialised on the watch
 * page because hls_manifest_url was always null in the API response.
 *
 * Root cause: CDN_BASE_URL was missing from the --set-env-vars flag in the Cloud Run
 * deploy step of deploy-api.yml.  Without it, cdnURLFromGCSPath() in
 * api/internal/handler/video.go returns an empty string instead of converting the
 * stored GCS path (gs://mytube-hls-output/videos/<id>/index.m3u8) to a public HTTP
 * CDN URL.  The frontend received hls_manifest_url: null, skipped rendering
 * VideoPlayer, and showed "Video not available yet." for every video.
 */

import * as fs from "fs";
import * as path from "path";

describe("deploy-api.yml workflow configuration", () => {
  let workflowContent: string;

  beforeAll(() => {
    const workflowPath = path.resolve(
      __dirname,
      "../../../../.github/workflows/deploy-api.yml"
    );
    workflowContent = fs.readFileSync(workflowPath, "utf8");
  });

  it("set-env-vars includes CDN_BASE_URL so cdnURLFromGCSPath returns a public HTTP URL", () => {
    // Without CDN_BASE_URL the API's cdnURLFromGCSPath() short-circuits and returns
    // the raw GCS path or empty string, causing hls_manifest_url to be null in every
    // GET /api/videos/:id response. The frontend then never renders VideoPlayer.
    expect(workflowContent).toContain("CDN_BASE_URL=");
  });
});
