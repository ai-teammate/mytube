/**
 * Unit tests for src/app/category/[id]/page.tsx
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import type { VideoCardItem, Category, CategoryRepository } from "@/domain/search";

// ─── Mock React.use to unwrap Promise synchronously in tests ──────────────────
jest.mock("react", () => {
  const actual = jest.requireActual<typeof React>("react");
  return {
    ...actual,
    use: jest.fn(<T,>(p: Promise<T> | T): T => {
      if (p && typeof (p as Promise<T>).then === "function") {
        return (p as unknown as { __value: T }).__value;
      }
      return p as T;
    }),
  };
});

// ─── Mock next/image ──────────────────────────────────────────────────────────
jest.mock("next/image", () => ({
  __esModule: true,
  default: function MockImage({
    src,
    alt,
    ...props
  }: {
    src: string;
    alt: string;
    [key: string]: unknown;
  }) {
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const { fill: _fill, ...rest } = props;
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={src} alt={alt} {...rest} />;
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
import CategoryPage from "@/app/category/[id]/CategoryPageClient";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function makeParams(id: string): Promise<{ id: string }> {
  const p = Promise.resolve({ id });
  (p as unknown as { __value: { id: string } }).__value = { id };
  return p;
}

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
  cats: Category[],
  videos: VideoCardItem[],
  opts: { catsError?: boolean; videosError?: boolean } = {}
): CategoryRepository {
  return {
    getAll: () =>
      opts.catsError
        ? Promise.reject(new Error("cats error"))
        : Promise.resolve(cats),
    getVideosByCategory: () =>
      opts.videosError
        ? Promise.reject(new Error("videos error"))
        : Promise.resolve(videos),
  };
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("CategoryPage", () => {
  it("shows skeleton loading state initially", () => {
    const repo: CategoryRepository = {
      getAll: () => new Promise(() => {}),
      getVideosByCategory: () => new Promise(() => {}),
    };

    render(<CategoryPage params={makeParams("1")} repository={repo} />);
    expect(screen.getAllByTestId("video-card-skeleton").length).toBeGreaterThan(0);
  });

  it("renders category name as heading when category is found", async () => {
    const cats: Category[] = [{ id: 1, name: "Education" }];
    const repo = makeRepo(cats, []);

    render(<CategoryPage params={makeParams("1")} repository={repo} />);

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: "Education" })
      ).toBeInTheDocument();
    });
  });

  it("renders fallback heading when category not found in list", async () => {
    const repo = makeRepo([], []);

    render(<CategoryPage params={makeParams("99")} repository={repo} />);

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: /category 99/i })
      ).toBeInTheDocument();
    });
  });

  it("renders video cards when videos are returned", async () => {
    const cats: Category[] = [{ id: 2, name: "Gaming" }];
    const videos = [
      makeVideo("v1", "Gaming Video 1"),
      makeVideo("v2", "Gaming Video 2"),
    ];
    const repo = makeRepo(cats, videos);

    render(<CategoryPage params={makeParams("2")} repository={repo} />);

    await waitFor(() => {
      expect(screen.getByText("Gaming Video 1")).toBeInTheDocument();
      expect(screen.getByText("Gaming Video 2")).toBeInTheDocument();
    });
  });

  it("shows 'No videos in this category yet' when empty", async () => {
    const cats: Category[] = [{ id: 1, name: "Music" }];
    const repo = makeRepo(cats, []);

    render(<CategoryPage params={makeParams("1")} repository={repo} />);

    await waitFor(() => {
      expect(
        screen.getByText(/no videos in this category yet/i)
      ).toBeInTheDocument();
    });
  });

  it("shows error message when repository throws", async () => {
    const repo = makeRepo([], [], { catsError: true });

    render(<CategoryPage params={makeParams("1")} repository={repo} />);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        /could not load category/i
      );
    });
  });

  it("shows error when category id is not a valid number", async () => {
    const repo = makeRepo([], []);

    render(<CategoryPage params={makeParams("invalid")} repository={repo} />);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        /invalid category/i
      );
    });
  });

  it("does not show loading after data loads", async () => {
    const repo = makeRepo([{ id: 3, name: "Music" }], []);

    render(<CategoryPage params={makeParams("3")} repository={repo} />);

    await waitFor(() => {
      expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
    });
  });

  it("calls getAll and getVideosByCategory on mount", async () => {
    const getAll = jest.fn(() => Promise.resolve([{ id: 1, name: "Education" }]));
    const getVideosByCategory = jest.fn(() => Promise.resolve([]));
    const repo: CategoryRepository = { getAll, getVideosByCategory };

    render(<CategoryPage params={makeParams("1")} repository={repo} />);

    await waitFor(() => {
      expect(getAll).toHaveBeenCalled();
      expect(getVideosByCategory).toHaveBeenCalledWith(1, 20, 0);
    });
  });
});
