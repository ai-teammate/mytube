/**
 * Unit tests for src/app/page.tsx (HomePage)
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import type { VideoCardItem, DiscoveryRepository } from "@/domain/search";

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

// ─── Mock next/navigation for SiteHeader ──────────────────────────────────────
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn() }),
}));

// ─── Mock AuthContext for SiteHeader ──────────────────────────────────────────
jest.mock("@/context/AuthContext", () => ({
  useAuth: () => ({ user: null, loading: false, signOut: jest.fn() }),
}));

// ─── Import page AFTER mocks ──────────────────────────────────────────────────
import HomePage from "@/app/HomePageClient";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function makeVideo(id: string, title: string): VideoCardItem {
  return {
    id,
    title,
    thumbnailUrl: null,
    viewCount: 10,
    uploaderUsername: "alice",
    createdAt: "2024-01-15T10:00:00Z",
  };
}

function makeRepo(
  getRecent: () => Promise<VideoCardItem[]>,
  getPopular: () => Promise<VideoCardItem[]>
): DiscoveryRepository {
  return { getRecent, getPopular };
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("HomePage", () => {
  it("shows loading state initially", () => {
    const repo = makeRepo(
      () => new Promise(() => {}),
      () => new Promise(() => {})
    );

    render(<HomePage repository={repo} />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("renders 'Recently Uploaded' section heading after load", async () => {
    const repo = makeRepo(
      () => Promise.resolve([makeVideo("v1", "Recent Video")]),
      () => Promise.resolve([])
    );

    render(<HomePage repository={repo} />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /recently uploaded/i })).toBeInTheDocument();
    });
  });

  it("renders 'Most Viewed' section heading after load", async () => {
    const repo = makeRepo(
      () => Promise.resolve([]),
      () => Promise.resolve([makeVideo("p1", "Popular Video")])
    );

    render(<HomePage repository={repo} />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /most viewed/i })).toBeInTheDocument();
    });
  });

  it("renders video cards in recently uploaded section", async () => {
    const repo = makeRepo(
      () => Promise.resolve([
        makeVideo("v1", "Recent Video 1"),
        makeVideo("v2", "Recent Video 2"),
      ]),
      () => Promise.resolve([])
    );

    render(<HomePage repository={repo} />);

    await waitFor(() => {
      expect(screen.getByText("Recent Video 1")).toBeInTheDocument();
      expect(screen.getByText("Recent Video 2")).toBeInTheDocument();
    });
  });

  it("renders video cards in most viewed section", async () => {
    const repo = makeRepo(
      () => Promise.resolve([]),
      () => Promise.resolve([makeVideo("p1", "Popular Video 1")])
    );

    render(<HomePage repository={repo} />);

    await waitFor(() => {
      expect(screen.getByText("Popular Video 1")).toBeInTheDocument();
    });
  });

  it("shows 'No videos yet' when recent videos is empty", async () => {
    const repo = makeRepo(
      () => Promise.resolve([]),
      () => Promise.resolve([])
    );

    render(<HomePage repository={repo} />);

    await waitFor(() => {
      // There will be two "No videos yet." for both sections
      const messages = screen.getAllByText("No videos yet.");
      expect(messages.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("shows error message when repository throws", async () => {
    const repo = makeRepo(
      () => Promise.reject(new Error("network failure")),
      () => Promise.reject(new Error("network failure"))
    );

    render(<HomePage repository={repo} />);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        /could not load videos/i
      );
    });
  });

  it("does not show loading state after data loads", async () => {
    const repo = makeRepo(
      () => Promise.resolve([]),
      () => Promise.resolve([])
    );

    render(<HomePage repository={repo} />);

    await waitFor(() => {
      expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
    });
  });

  it("calls getRecent and getPopular on mount", async () => {
    const getRecent = jest.fn(() => Promise.resolve([]));
    const getPopular = jest.fn(() => Promise.resolve([]));
    const repo: DiscoveryRepository = { getRecent, getPopular };

    render(<HomePage repository={repo} />);

    await waitFor(() => {
      expect(getRecent).toHaveBeenCalledWith(20);
      expect(getPopular).toHaveBeenCalledWith(20);
    });
  });

  // ─── Hero section ─────────────────────────────────────────────────────────

  it("renders the hero headline", () => {
    const repo = makeRepo(
      () => new Promise(() => {}),
      () => new Promise(() => {})
    );

    render(<HomePage repository={repo} />);
    expect(
      screen.getByRole("heading", { level: 1, name: /mytube: personal video portal/i })
    ).toBeInTheDocument();
  });

  it("renders all three feature pills", () => {
    const repo = makeRepo(
      () => new Promise(() => {}),
      () => new Promise(() => {})
    );

    render(<HomePage repository={repo} />);
    expect(screen.getByText("Upload & Share")).toBeInTheDocument();
    expect(screen.getByText("HLS Streaming")).toBeInTheDocument();
    expect(screen.getByText("Playlists & Discovery")).toBeInTheDocument();
  });

  it("renders the hero sub-text paragraph", () => {
    const repo = makeRepo(
      () => new Promise(() => {}),
      () => new Promise(() => {})
    );

    render(<HomePage repository={repo} />);
    expect(
      screen.getByText(/your personal space to upload, stream, and discover videos/i)
    ).toBeInTheDocument();
  });

  it("renders the 'Browse Library' CTA button in the hero section", () => {
    const repo = makeRepo(
      () => new Promise(() => {}),
      () => new Promise(() => {})
    );

    render(<HomePage repository={repo} />);
    const btn = screen.getByRole("button", { name: /browse library/i });
    expect(btn).toBeInTheDocument();
  });

  it("clicking 'Browse Library' calls scrollIntoView on the video-grid element", () => {
    const repo = makeRepo(
      () => new Promise(() => {}),
      () => new Promise(() => {})
    );

    const scrollIntoViewMock = jest.fn();
    const videoGridDiv = document.createElement("section");
    videoGridDiv.id = "video-grid";
    videoGridDiv.scrollIntoView = scrollIntoViewMock;
    document.body.appendChild(videoGridDiv);

    render(<HomePage repository={repo} />);
    const btn = screen.getByRole("button", { name: /browse library/i });
    btn.click();

    expect(scrollIntoViewMock).toHaveBeenCalledWith({ behavior: "smooth" });

    document.body.removeChild(videoGridDiv);
  });

  it("the video grid section has id='video-grid' as smooth-scroll anchor", async () => {
    const repo = makeRepo(
      () => Promise.resolve([]),
      () => Promise.resolve([])
    );

    render(<HomePage repository={repo} />);

    await waitFor(() => {
      const section = document.getElementById("video-grid");
      expect(section).not.toBeNull();
    });
  });

  it("renders 'Upload Your First Video' link in the hero", () => {
    const repo = makeRepo(
      () => new Promise(() => {}),
      () => new Promise(() => {})
    );

    render(<HomePage repository={repo} />);
    const link = screen.getByRole("link", { name: /upload your first video/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "/upload");
  });

  it("always renders landing_image.png in the hero visual panel", async () => {
    const videoWithThumb = { ...makeVideo("v1", "Thumb Video"), thumbnailUrl: "https://cdn.example.com/thumb.jpg" };
    const repo = makeRepo(
      () => Promise.resolve([videoWithThumb]),
      () => Promise.resolve([])
    );

    render(<HomePage repository={repo} />);

    await waitFor(() => {
      const img = screen.getByAltText("Personal Playback Preview");
      expect(img).toHaveAttribute("src", "/landing_image.png");
    });
  });

  it("renders landing_image.png when no videos have thumbnails", async () => {
    const repo = makeRepo(
      () => Promise.resolve([makeVideo("v1", "No Thumb")]),
      () => Promise.resolve([])
    );

    render(<HomePage repository={repo} />);

    await waitFor(() => {
      const img = screen.getByAltText("Personal Playback Preview");
      expect(img).toHaveAttribute("src", "/landing_image.png");
    });
  });

  it("renders all three stat cards in the hero", () => {
    const repo = makeRepo(
      () => new Promise(() => {}),
      () => new Promise(() => {})
    );

    render(<HomePage repository={repo} />);
    expect(screen.getByText("100% Private")).toBeInTheDocument();
    expect(screen.getByText("HLS Quality")).toBeInTheDocument();
    expect(screen.getByText("Free Forever")).toBeInTheDocument();
  });
});
