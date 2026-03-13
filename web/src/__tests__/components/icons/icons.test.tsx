/**
 * Unit tests for web/src/components/icons/
 * Covers all seven icon components and the barrel export.
 */
import React from "react";
import { render } from "@testing-library/react";
import {
  LogoIcon,
  DecorPlay,
  DecorFilm,
  DecorCamera,
  DecorWave,
  SunIcon,
  MoonIcon,
} from "@/components/icons";

// ─── Helpers ──────────────────────────────────────────────────────────────────

/** Queries the first <svg> in the rendered output. */
function getSvg(container: HTMLElement): SVGSVGElement {
  const el = container.querySelector("svg");
  if (!el) throw new Error("No <svg> found");
  return el as SVGSVGElement;
}

// ─── LogoIcon ─────────────────────────────────────────────────────────────────

describe("LogoIcon", () => {
  it("renders an <svg> element", () => {
    const { container } = render(<LogoIcon />);
    expect(getSvg(container)).toBeInTheDocument();
  });

  it("has viewBox 0 0 40 40", () => {
    const { container } = render(<LogoIcon />);
    expect(getSvg(container)).toHaveAttribute("viewBox", "0 0 40 40");
  });

  it("has fill=none on the root svg", () => {
    const { container } = render(<LogoIcon />);
    expect(getSvg(container)).toHaveAttribute("fill", "none");
  });

  it("defaults to aria-hidden=true", () => {
    const { container } = render(<LogoIcon />);
    expect(getSvg(container)).toHaveAttribute("aria-hidden", "true");
  });

  it("accepts a className prop", () => {
    const { container } = render(<LogoIcon className="text-red-600 h-8 w-8" />);
    expect(getSvg(container)).toHaveClass("text-red-600", "h-8", "w-8");
  });

  it("accepts a style prop", () => {
    const { container } = render(<LogoIcon style={{ color: "rgb(255, 0, 0)" }} />);
    expect(getSvg(container)).toHaveStyle({ color: "rgb(255, 0, 0)" });
  });

  it("allows aria-hidden to be overridden to false", () => {
    const { container } = render(
      <LogoIcon aria-hidden={false} aria-label="mytube logo" role="img" />
    );
    expect(getSvg(container)).toHaveAttribute("aria-hidden", "false");
    expect(getSvg(container)).toHaveAttribute("aria-label", "mytube logo");
  });

  it("forwards extra SVG props", () => {
    const { container } = render(<LogoIcon data-testid="logo-icon" />);
    expect(getSvg(container)).toHaveAttribute("data-testid", "logo-icon");
  });

  it("renders a rounded-rect background shape", () => {
    const { container } = render(<LogoIcon />);
    const rect = container.querySelector("rect");
    expect(rect).toBeInTheDocument();
    expect(rect).toHaveAttribute("rx", "10");
  });

  it("renders a linearGradient in <defs>", () => {
    const { container } = render(<LogoIcon />);
    const defs = container.querySelector("defs");
    expect(defs).toBeInTheDocument();
    const grad = defs!.querySelector("linearGradient");
    expect(grad).toBeInTheDocument();
  });

  it("gradient start stop uses var(--logo-grad-start)", () => {
    const { container } = render(<LogoIcon />);
    const stops = container.querySelectorAll("stop");
    expect(stops[0]).toHaveAttribute("stop-color", "var(--logo-grad-start)");
  });

  it("gradient end stop uses var(--logo-grad-end)", () => {
    const { container } = render(<LogoIcon />);
    const stops = container.querySelectorAll("stop");
    expect(stops[1]).toHaveAttribute("stop-color", "var(--logo-grad-end)");
  });

  it("rect fill references the gradient id", () => {
    const { container } = render(<LogoIcon />);
    const rect = container.querySelector("rect");
    const grad = container.querySelector("linearGradient");
    const gradId = grad!.getAttribute("id")!;
    expect(rect).toHaveAttribute("fill", `url(#${gradId})`);
  });

  it("each instance gets a unique gradient id", () => {
    const { container: c1 } = render(<LogoIcon />);
    const { container: c2 } = render(<LogoIcon />);
    const id1 = c1.querySelector("linearGradient")!.getAttribute("id");
    const id2 = c2.querySelector("linearGradient")!.getAttribute("id");
    expect(id1).not.toBe(id2);
  });

  it("renders play triangle path with white fill", () => {
    const { container } = render(<LogoIcon />);
    const paths = container.querySelectorAll("path");
    const playPath = Array.from(paths).find((p) => p.getAttribute("fill") === "white");
    expect(playPath).toBeInTheDocument();
  });

  it("renders smile arc path with white stroke", () => {
    const { container } = render(<LogoIcon />);
    const paths = container.querySelectorAll("path");
    const smilePath = Array.from(paths).find(
      (p) => p.getAttribute("stroke") === "white" && p.getAttribute("fill") !== "white"
    );
    expect(smilePath).toBeInTheDocument();
  });
});

// ─── DecorPlay ────────────────────────────────────────────────────────────────

describe("DecorPlay", () => {
  it("renders an <svg> element", () => {
    const { container } = render(<DecorPlay />);
    expect(getSvg(container)).toBeInTheDocument();
  });

  it("has viewBox 0 0 120 120", () => {
    const { container } = render(<DecorPlay />);
    expect(getSvg(container)).toHaveAttribute("viewBox", "0 0 120 120");
  });

  it("has fill=currentColor", () => {
    const { container } = render(<DecorPlay />);
    expect(getSvg(container)).toHaveAttribute("fill", "currentColor");
  });

  it("defaults to aria-hidden=true", () => {
    const { container } = render(<DecorPlay />);
    expect(getSvg(container)).toHaveAttribute("aria-hidden", "true");
  });

  it("accepts a className prop", () => {
    const { container } = render(<DecorPlay className="opacity-20" />);
    expect(getSvg(container)).toHaveClass("opacity-20");
  });

  it("accepts a style prop", () => {
    const { container } = render(<DecorPlay style={{ opacity: 0.5 }} />);
    expect(getSvg(container)).toHaveStyle({ opacity: "0.5" });
  });

  it("allows aria-hidden to be overridden to false", () => {
    const { container } = render(
      <DecorPlay aria-hidden={false} aria-label="decorative play shape" role="img" />
    );
    expect(getSvg(container)).toHaveAttribute("aria-hidden", "false");
    expect(getSvg(container)).toHaveAttribute("aria-label", "decorative play shape");
  });

  it("forwards extra SVG props", () => {
    const { container } = render(<DecorPlay data-testid="decor-play" />);
    expect(getSvg(container)).toHaveAttribute("data-testid", "decor-play");
  });
});

// ─── DecorFilm ────────────────────────────────────────────────────────────────

describe("DecorFilm", () => {
  it("renders an <svg> element", () => {
    const { container } = render(<DecorFilm />);
    expect(getSvg(container)).toBeInTheDocument();
  });

  it("has viewBox 0 0 120 120", () => {
    const { container } = render(<DecorFilm />);
    expect(getSvg(container)).toHaveAttribute("viewBox", "0 0 120 120");
  });

  it("has fill=currentColor", () => {
    const { container } = render(<DecorFilm />);
    expect(getSvg(container)).toHaveAttribute("fill", "currentColor");
  });

  it("defaults to aria-hidden=true", () => {
    const { container } = render(<DecorFilm />);
    expect(getSvg(container)).toHaveAttribute("aria-hidden", "true");
  });

  it("accepts a className prop", () => {
    const { container } = render(<DecorFilm className="text-blue-400" />);
    expect(getSvg(container)).toHaveClass("text-blue-400");
  });

  it("accepts a style prop", () => {
    const { container } = render(<DecorFilm style={{ opacity: 0.3 }} />);
    expect(getSvg(container)).toHaveStyle({ opacity: "0.3" });
  });

  it("allows aria-hidden to be overridden to false", () => {
    const { container } = render(
      <DecorFilm aria-hidden={false} aria-label="decorative film shape" role="img" />
    );
    expect(getSvg(container)).toHaveAttribute("aria-hidden", "false");
    expect(getSvg(container)).toHaveAttribute("aria-label", "decorative film shape");
  });

  it("forwards extra SVG props", () => {
    const { container } = render(<DecorFilm data-testid="decor-film" />);
    expect(getSvg(container)).toHaveAttribute("data-testid", "decor-film");
  });
});

// ─── DecorCamera ──────────────────────────────────────────────────────────────

describe("DecorCamera", () => {
  it("renders an <svg> element", () => {
    const { container } = render(<DecorCamera />);
    expect(getSvg(container)).toBeInTheDocument();
  });

  it("has viewBox 0 0 120 120", () => {
    const { container } = render(<DecorCamera />);
    expect(getSvg(container)).toHaveAttribute("viewBox", "0 0 120 120");
  });

  it("has fill=currentColor", () => {
    const { container } = render(<DecorCamera />);
    expect(getSvg(container)).toHaveAttribute("fill", "currentColor");
  });

  it("defaults to aria-hidden=true", () => {
    const { container } = render(<DecorCamera />);
    expect(getSvg(container)).toHaveAttribute("aria-hidden", "true");
  });

  it("accepts a className prop", () => {
    const { container } = render(<DecorCamera className="rotate-12" />);
    expect(getSvg(container)).toHaveClass("rotate-12");
  });

  it("accepts a style prop", () => {
    const { container } = render(<DecorCamera style={{ opacity: 0.4 }} />);
    expect(getSvg(container)).toHaveStyle({ opacity: "0.4" });
  });

  it("allows aria-hidden to be overridden to false", () => {
    const { container } = render(
      <DecorCamera aria-hidden={false} aria-label="decorative camera shape" role="img" />
    );
    expect(getSvg(container)).toHaveAttribute("aria-hidden", "false");
    expect(getSvg(container)).toHaveAttribute("aria-label", "decorative camera shape");
  });

  it("forwards extra SVG props", () => {
    const { container } = render(<DecorCamera data-testid="decor-camera" />);
    expect(getSvg(container)).toHaveAttribute("data-testid", "decor-camera");
  });
});

// ─── DecorWave ────────────────────────────────────────────────────────────────

describe("DecorWave", () => {
  it("renders an <svg> element", () => {
    const { container } = render(<DecorWave />);
    expect(getSvg(container)).toBeInTheDocument();
  });

  it("has viewBox 0 0 120 120", () => {
    const { container } = render(<DecorWave />);
    expect(getSvg(container)).toHaveAttribute("viewBox", "0 0 120 120");
  });

  it("has fill=currentColor", () => {
    const { container } = render(<DecorWave />);
    expect(getSvg(container)).toHaveAttribute("fill", "currentColor");
  });

  it("defaults to aria-hidden=true", () => {
    const { container } = render(<DecorWave />);
    expect(getSvg(container)).toHaveAttribute("aria-hidden", "true");
  });

  it("accepts a className prop", () => {
    const { container } = render(<DecorWave className="text-purple-500" />);
    expect(getSvg(container)).toHaveClass("text-purple-500");
  });

  it("accepts a style prop", () => {
    const { container } = render(<DecorWave style={{ opacity: 0.6 }} />);
    expect(getSvg(container)).toHaveStyle({ opacity: "0.6" });
  });

  it("allows aria-hidden to be overridden to false", () => {
    const { container } = render(
      <DecorWave aria-hidden={false} aria-label="decorative wave shape" role="img" />
    );
    expect(getSvg(container)).toHaveAttribute("aria-hidden", "false");
    expect(getSvg(container)).toHaveAttribute("aria-label", "decorative wave shape");
  });

  it("forwards extra SVG props", () => {
    const { container } = render(<DecorWave data-testid="decor-wave" />);
    expect(getSvg(container)).toHaveAttribute("data-testid", "decor-wave");
  });
});

// ─── SunIcon ──────────────────────────────────────────────────────────────────

describe("SunIcon", () => {
  it("renders an <svg> element", () => {
    const { container } = render(<SunIcon />);
    expect(getSvg(container)).toBeInTheDocument();
  });

  it("has viewBox 0 0 24 24", () => {
    const { container } = render(<SunIcon />);
    expect(getSvg(container)).toHaveAttribute("viewBox", "0 0 24 24");
  });

  it("uses stroke rendering (fill=none)", () => {
    const { container } = render(<SunIcon />);
    expect(getSvg(container)).toHaveAttribute("fill", "none");
    expect(getSvg(container)).toHaveAttribute("stroke", "currentColor");
  });

  it("has strokeWidth=2", () => {
    const { container } = render(<SunIcon />);
    expect(getSvg(container)).toHaveAttribute("stroke-width", "2");
  });

  it("defaults to aria-hidden=true", () => {
    const { container } = render(<SunIcon />);
    expect(getSvg(container)).toHaveAttribute("aria-hidden", "true");
  });

  it("accepts a className prop", () => {
    const { container } = render(<SunIcon className="text-yellow-500 h-5 w-5" />);
    expect(getSvg(container)).toHaveClass("text-yellow-500", "h-5", "w-5");
  });

  it("accepts a style prop", () => {
    const { container } = render(<SunIcon style={{ width: 20 }} />);
    expect(getSvg(container)).toHaveStyle({ width: "20px" });
  });

  it("allows aria-hidden to be overridden", () => {
    const { container } = render(
      <SunIcon aria-hidden={false} aria-label="Switch to light mode" role="img" />
    );
    expect(getSvg(container)).toHaveAttribute("aria-hidden", "false");
    expect(getSvg(container)).toHaveAttribute("aria-label", "Switch to light mode");
  });

  it("forwards extra SVG props", () => {
    const { container } = render(<SunIcon data-testid="sun-icon" />);
    expect(getSvg(container)).toHaveAttribute("data-testid", "sun-icon");
  });
});

// ─── MoonIcon ─────────────────────────────────────────────────────────────────

describe("MoonIcon", () => {
  it("renders an <svg> element", () => {
    const { container } = render(<MoonIcon />);
    expect(getSvg(container)).toBeInTheDocument();
  });

  it("has viewBox 0 0 24 24", () => {
    const { container } = render(<MoonIcon />);
    expect(getSvg(container)).toHaveAttribute("viewBox", "0 0 24 24");
  });

  it("uses stroke rendering (fill=none)", () => {
    const { container } = render(<MoonIcon />);
    expect(getSvg(container)).toHaveAttribute("fill", "none");
    expect(getSvg(container)).toHaveAttribute("stroke", "currentColor");
  });

  it("has strokeWidth=2", () => {
    const { container } = render(<MoonIcon />);
    expect(getSvg(container)).toHaveAttribute("stroke-width", "2");
  });

  it("defaults to aria-hidden=true", () => {
    const { container } = render(<MoonIcon />);
    expect(getSvg(container)).toHaveAttribute("aria-hidden", "true");
  });

  it("accepts a className prop", () => {
    const { container } = render(<MoonIcon className="text-indigo-400 h-5 w-5" />);
    expect(getSvg(container)).toHaveClass("text-indigo-400", "h-5", "w-5");
  });

  it("accepts a style prop", () => {
    const { container } = render(<MoonIcon style={{ height: 20 }} />);
    expect(getSvg(container)).toHaveStyle({ height: "20px" });
  });

  it("allows aria-hidden to be overridden", () => {
    const { container } = render(
      <MoonIcon aria-hidden={false} aria-label="Switch to dark mode" role="img" />
    );
    expect(getSvg(container)).toHaveAttribute("aria-hidden", "false");
    expect(getSvg(container)).toHaveAttribute("aria-label", "Switch to dark mode");
  });

  it("forwards extra SVG props", () => {
    const { container } = render(<MoonIcon data-testid="moon-icon" />);
    expect(getSvg(container)).toHaveAttribute("data-testid", "moon-icon");
  });
});

// ─── Barrel export ────────────────────────────────────────────────────────────

describe("icons barrel export", () => {
  it("exports LogoIcon as a function", () => {
    expect(typeof LogoIcon).toBe("function");
  });

  it("exports DecorPlay as a function", () => {
    expect(typeof DecorPlay).toBe("function");
  });

  it("exports DecorFilm as a function", () => {
    expect(typeof DecorFilm).toBe("function");
  });

  it("exports DecorCamera as a function", () => {
    expect(typeof DecorCamera).toBe("function");
  });

  it("exports DecorWave as a function", () => {
    expect(typeof DecorWave).toBe("function");
  });

  it("exports SunIcon as a function", () => {
    expect(typeof SunIcon).toBe("function");
  });

  it("exports MoonIcon as a function", () => {
    expect(typeof MoonIcon).toBe("function");
  });
});
