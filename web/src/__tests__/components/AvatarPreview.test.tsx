/**
 * Unit tests for src/components/AvatarPreview.tsx
 */
import React from "react";
import { render, screen, fireEvent, act } from "@testing-library/react";
import AvatarPreview from "@/components/AvatarPreview";

describe("AvatarPreview", () => {
  it("renders a placeholder when src is empty string", () => {
    render(<AvatarPreview src="" />);
    // Container always has role="img" and aria-label; inner <img> is absent.
    const container = screen.getByRole("img", { name: /avatar preview/i });
    expect(container).toBeInTheDocument();
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("svg")).toBeInTheDocument();
  });

  it("renders an img element when src is non-empty", () => {
    render(<AvatarPreview src="https://example.com/avatar.png" />);
    const container = screen.getByRole("img", { name: /avatar preview/i });
    const img = container.querySelector("img");
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute("src", "https://example.com/avatar.png");
  });

  it("applies rounded-full and object-cover classes to the img", () => {
    render(<AvatarPreview src="https://example.com/avatar.png" />);
    const container = screen.getByRole("img", { name: /avatar preview/i });
    const img = container.querySelector("img")!;
    expect(img).toHaveClass("rounded-full");
    expect(img).toHaveClass("object-cover");
    expect(img).toHaveClass("w-16");
    expect(img).toHaveClass("h-16");
  });

  it("shows placeholder on image load error", () => {
    render(<AvatarPreview src="https://broken.example.com/avatar.png" />);

    const container = screen.getByRole("img", { name: /avatar preview/i });
    const img = container.querySelector("img")!;
    act(() => {
      fireEvent.error(img);
    });

    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("svg")).toBeInTheDocument();
  });

  it("resets error state when src changes", () => {
    const { rerender } = render(
      <AvatarPreview src="https://broken.example.com/avatar.png" />
    );

    const container = screen.getByRole("img", { name: /avatar preview/i });
    const img = container.querySelector("img")!;
    act(() => {
      fireEvent.error(img);
    });

    // Should now show placeholder
    expect(container.querySelector("img")).toBeNull();

    // Update with a new URL — error state should reset and img should appear
    rerender(<AvatarPreview src="https://example.com/new-avatar.png" />);
    expect(container.querySelector("img")).toBeInTheDocument();
  });

  it("shows placeholder when src becomes empty after having a value", () => {
    const { rerender } = render(
      <AvatarPreview src="https://example.com/avatar.png" />
    );
    const container = screen.getByRole("img", { name: /avatar preview/i });
    expect(container.querySelector("img")).toBeInTheDocument();

    rerender(<AvatarPreview src="" />);
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("svg")).toBeInTheDocument();
  });

  it("container always has rounded-full and bg-gray-200 classes", () => {
    render(<AvatarPreview src="" />);
    const container = screen.getByRole("img", { name: /avatar preview/i });
    expect(container).toHaveClass("rounded-full");
    expect(container).toHaveClass("bg-gray-200");
    expect(container).toHaveClass("w-16");
    expect(container).toHaveClass("h-16");
  });
});
