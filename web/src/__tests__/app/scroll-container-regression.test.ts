/**
 * Regression test for MYTUBE-537: page scrolling unresponsive.
 *
 * Root cause: `overflow: hidden` on `.shell` and `overflow-x: hidden` on
 * `.page-wrap` create implicit scroll containers (per CSS spec).  The browser
 * silently routes scroll events to those containers, which have no visible
 * overflow, so the user perceives the page as non-scrollable until the
 * containers' scrollTop is exhausted.
 *
 * Fix: both values must be `clip`, which provides identical visual clipping
 * WITHOUT creating a scroll container.
 */

import * as fs from "fs";
import * as path from "path";

const GLOBALS_CSS = path.resolve(__dirname, "../../app/globals.css");

function extractRules(css: string): Map<string, Record<string, string>> {
  // Strip block comments before parsing to avoid /* ... : ... */ confusing the parser
  const stripped = css.replace(/\/\*[\s\S]*?\*\//g, "");
  const rules = new Map<string, Record<string, string>>();
  // Match simple .selector { ... } blocks (no nested rules)
  const rulePattern = /([^{}@]+)\{([^{}]*)\}/g;
  let match: RegExpExecArray | null;
  while ((match = rulePattern.exec(stripped)) !== null) {
    const selector = match[1].trim();
    const body = match[2];
    const decls: Record<string, string> = {};
    for (const decl of body.split(";")) {
      const colon = decl.indexOf(":");
      if (colon === -1) continue;
      const prop = decl.slice(0, colon).trim();
      const val = decl.slice(colon + 1).trim();
      if (prop) decls[prop] = val;
    }
    // Merge multiple rule blocks for the same selector
    rules.set(selector, { ...(rules.get(selector) ?? {}), ...decls });
  }
  return rules;
}

describe("globals.css scroll-container regression (MYTUBE-537)", () => {
  let rules: Map<string, Record<string, string>>;

  beforeAll(() => {
    const css = fs.readFileSync(GLOBALS_CSS, "utf8");
    rules = extractRules(css);
  });

  describe(".page-wrap", () => {
    it("uses overflow-x: clip, not overflow-x: hidden (hidden creates an implicit y scroll-container)", () => {
      const decls = rules.get(".page-wrap") ?? {};
      // Must NOT be hidden
      expect(decls["overflow-x"]).not.toBe("hidden");
      expect(decls["overflow"]).not.toBe("hidden");
      // Must be clip (the non-scroll-container clipping value)
      expect(decls["overflow-x"]).toBe("clip");
    });
  });

  describe(".shell", () => {
    it("uses overflow: clip, not overflow: hidden (hidden creates a scroll-container that silently consumes scroll events)", () => {
      const decls = rules.get(".shell") ?? {};
      // Must NOT be hidden
      expect(decls["overflow"]).not.toBe("hidden");
      // Must be clip
      expect(decls["overflow"]).toBe("clip");
    });
  });
});
