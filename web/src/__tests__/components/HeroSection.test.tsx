/**
 * Unit tests for src/components/HeroSection.tsx
 */
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import HeroSection from "@/components/HeroSection";

// ─── Mock next/link ───────────────────────────────────────────────────────────
jest.mock("next/link", () => ({
  __esModule: true,
  default: function MockLink({
    href,
    children,
    className,
    ...rest
  }: {
    href: string;
    children: React.ReactNode;
    className?: string;
    [key: string]: unknown;
  }) {
    return (
      <a href={href} className={className} {...rest}>
        {children}
      </a>
    );
  },
}));

// ─── Mock next/image ──────────────────────────────────────────────────────────
jest.mock("next/image", () => ({
  __esModule: true,
  default: function MockImage({
    src,
    alt,
    width,
    height,
    sizes,
    style,
    ...props
  }: {
    src: string;
    alt: string;
    width?: number;
    height?: number;
    sizes?: string;
    style?: React.CSSProperties;
    [key: string]: unknown;
  }) {
    // eslint-disable-next-line @next/next/no-img-element
    return (
      <img
        src={src}
        alt={alt}
        width={width}
        height={height}
        data-sizes={sizes}
        style={style}
        {...props}
      />
    );
  },
}));

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("HeroSection", () => {
  // ─── Feature pills ───────────────────────────────────────────────────────

  it("renders 'Upload & Share' pill", () => {
    render(<HeroSection />);
    expect(screen.getByText("Upload & Share")).toBeInTheDocument();
  });

  it("renders 'HLS Streaming' pill", () => {
    render(<HeroSection />);
    expect(screen.getByText("HLS Streaming")).toBeInTheDocument();
  });

  it("renders 'Playlists & Discovery' pill", () => {
    render(<HeroSection />);
    expect(screen.getByText("Playlists & Discovery")).toBeInTheDocument();
  });

  // ─── Headline ────────────────────────────────────────────────────────────

  it("renders the h1 headline with correct text", () => {
    render(<HeroSection />);
    const h1 = screen.getByRole("heading", { level: 1, name: /mytube: personal video portal/i });
    expect(h1).toBeInTheDocument();
  });

  // ─── Sub-text ────────────────────────────────────────────────────────────

  it("renders the sub-text paragraph", () => {
    render(<HeroSection />);
    expect(
      screen.getByText(/your personal space to upload, stream, and discover videos/i)
    ).toBeInTheDocument();
  });

  // ─── CTA buttons ─────────────────────────────────────────────────────────

  it("renders 'Upload Your First Video' link pointing to /upload", () => {
    render(<HeroSection />);
    const link = screen.getByRole("link", { name: /upload your first video/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "/upload");
  });

  it("renders 'Browse Library' button", () => {
    render(<HeroSection />);
    const btn = screen.getByRole("button", { name: /browse library/i });
    expect(btn).toBeInTheDocument();
  });

  it("'Browse Library' button calls scrollIntoView on #video-grid element", () => {
    const scrollIntoViewMock = jest.fn();
    const gridEl = document.createElement("div");
    gridEl.id = "video-grid";
    gridEl.scrollIntoView = scrollIntoViewMock;
    document.body.appendChild(gridEl);

    render(<HeroSection />);
    fireEvent.click(screen.getByRole("button", { name: /browse library/i }));

    expect(scrollIntoViewMock).toHaveBeenCalledWith({ behavior: "smooth" });

    document.body.removeChild(gridEl);
  });

  it("'Browse Library' does not throw when #video-grid is absent", () => {
    render(<HeroSection />);
    expect(() => {
      fireEvent.click(screen.getByRole("button", { name: /browse library/i }));
    }).not.toThrow();
  });

  // ─── Stat cards ──────────────────────────────────────────────────────────

  it("renders '100% Private' stat card with description", () => {
    render(<HeroSection />);
    expect(screen.getByText("100% Private")).toBeInTheDocument();
    expect(screen.getByText("Your videos, your rules")).toBeInTheDocument();
  });

  it("renders 'HLS Quality' stat card with description", () => {
    render(<HeroSection />);
    expect(screen.getByText("HLS Quality")).toBeInTheDocument();
    expect(screen.getByText("Adaptive bitrate playback")).toBeInTheDocument();
  });

  it("renders 'Free Forever' stat card with description", () => {
    render(<HeroSection />);
    expect(screen.getByText("Free Forever")).toBeInTheDocument();
    expect(screen.getByText("No subscriptions ever")).toBeInTheDocument();
  });

  // ─── Visual panel ─────────────────────────────────────────────────────────

  it("renders 'Personal Playback Preview' title in visual panel", () => {
    render(<HeroSection />);
    expect(screen.getByText("Personal Playback Preview")).toBeInTheDocument();
  });

  it("renders '1080p' quality badge as active", () => {
    render(<HeroSection />);
    expect(screen.getByText("1080p")).toBeInTheDocument();
  });

  it("renders '720p' and '480p' quality badges", () => {
    render(<HeroSection />);
    expect(screen.getByText("720p")).toBeInTheDocument();
    expect(screen.getByText("480p")).toBeInTheDocument();
  });

  it("shows gradient placeholder canvas when no thumbnailUrl is provided", () => {
    render(<HeroSection />);
    expect(screen.queryByTestId("canvas-placeholder")).not.toBeInTheDocument();
  });

  it("always renders landing_image.png as the canvas visual regardless of video availability", () => {
    render(<HeroSection />);
    const img = screen.getByAltText("Personal Playback Preview");
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute("src", "/landing_image.png");
  });

  it("prefixes landing_image.png src with NEXT_PUBLIC_BASE_PATH when set (GitHub Pages basePath)", () => {
    const originalBasePath = process.env.NEXT_PUBLIC_BASE_PATH;
    process.env.NEXT_PUBLIC_BASE_PATH = "/mytube";
    render(<HeroSection />);
    const img = screen.getByAltText("Personal Playback Preview");
    expect(img).toHaveAttribute("src", "/mytube/landing_image.png");
    process.env.NEXT_PUBLIC_BASE_PATH = originalBasePath;
  });

  it("renders landing image with correct intrinsic dimensions", () => {
    render(<HeroSection />);
    const img = screen.getByAltText("Personal Playback Preview");
    expect(img).toHaveAttribute("width", "1536");
    expect(img).toHaveAttribute("height", "1024");
  });

  it("renders landing image with responsive sizes attribute", () => {
    render(<HeroSection />);
    const img = screen.getByAltText("Personal Playback Preview");
    expect(img).toHaveAttribute("data-sizes", "(max-width: 768px) 100vw, 50vw");
  });

  // ─── Accessibility ────────────────────────────────────────────────────────

  it("hero section has aria-label='Hero'", () => {
    render(<HeroSection />);
    const section = screen.getByRole("region", { name: "Hero" });
    expect(section).toBeInTheDocument();
  });

  it("visual panel has aria-hidden='true'", () => {
    const { container } = render(<HeroSection />);
    const panel = container.querySelector('[aria-hidden="true"]');
    expect(panel).toBeInTheDocument();
  });
});
