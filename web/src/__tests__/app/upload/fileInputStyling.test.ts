/**
 * Regression test for MYTUBE-591:
 * Verifies that the .fileInput CSS class in upload.module.css
 * includes ::file-selector-button styling so the Choose File button
 * is visible in both light and dark themes.
 */
import fs from "fs";
import path from "path";

const CSS_PATH = path.resolve(
  __dirname,
  "../../../app/upload/upload.module.css"
);

describe("upload.module.css — .fileInput ::file-selector-button styling", () => {
  let cssContent: string;

  beforeAll(() => {
    cssContent = fs.readFileSync(CSS_PATH, "utf-8");
  });

  it("defines ::file-selector-button rule inside .fileInput", () => {
    // The button must be styled so it is visible in dark theme
    expect(cssContent).toMatch(/\.fileInput\s*::\s*file-selector-button/);
  });

  it("sets a background colour on ::file-selector-button", () => {
    // Extract the ::file-selector-button block
    const match = cssContent.match(
      /\.fileInput\s*::\s*file-selector-button\s*\{([^}]*)\}/s
    );
    expect(match).not.toBeNull();
    const block = match![1];
    expect(block).toMatch(/background/);
  });

  it("sets a text colour on ::file-selector-button", () => {
    const match = cssContent.match(
      /\.fileInput\s*::\s*file-selector-button\s*\{([^}]*)\}/s
    );
    expect(match).not.toBeNull();
    const block = match![1];
    expect(block).toMatch(/color/);
  });
});
