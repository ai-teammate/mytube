/**
 * Unit tests for src/components/Skeleton.tsx
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import Skeleton from "@/components/Skeleton";

describe("Skeleton", () => {
  it("renders a div with aria-hidden", () => {
    const { container } = render(<Skeleton />);
    const el = container.firstChild as HTMLElement;
    expect(el).toBeInTheDocument();
    expect(el.getAttribute("aria-hidden")).toBe("true");
  });

  it("applies provided width style", () => {
    const { container } = render(<Skeleton width="200px" />);
    const el = container.firstChild as HTMLElement;
    expect(el.style.width).toBe("200px");
  });

  it("applies provided height style", () => {
    const { container } = render(<Skeleton height="40px" />);
    const el = container.firstChild as HTMLElement;
    expect(el.style.height).toBe("40px");
  });

  it("applies provided borderRadius style", () => {
    const { container } = render(<Skeleton borderRadius="50%" />);
    const el = container.firstChild as HTMLElement;
    expect(el.style.borderRadius).toBe("50%");
  });

  it("merges extra className with the module class", () => {
    const { container } = render(<Skeleton className="extra-class" />);
    const el = container.firstChild as HTMLElement;
    expect(el.className).toContain("extra-class");
  });

  it("renders without any optional props", () => {
    const { container } = render(<Skeleton />);
    expect(container.firstChild).toBeInTheDocument();
  });

  it("does not set style properties when not provided", () => {
    const { container } = render(<Skeleton />);
    const el = container.firstChild as HTMLElement;
    expect(el.style.width).toBe("");
    expect(el.style.height).toBe("");
    expect(el.style.borderRadius).toBe("");
  });

  it("accepts all style props together", () => {
    const { container } = render(
      <Skeleton width="100px" height="20px" borderRadius="4px" />
    );
    const el = container.firstChild as HTMLElement;
    expect(el.style.width).toBe("100px");
    expect(el.style.height).toBe("20px");
    expect(el.style.borderRadius).toBe("4px");
  });
});
