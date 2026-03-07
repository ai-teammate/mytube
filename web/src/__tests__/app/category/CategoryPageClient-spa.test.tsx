/**
 * Reproduction test for MYTUBE-285: Category browse page /category/[id]/
 * broken on GitHub Pages — dynamic ID replaced with _ showing "Invalid category."
 *
 * Root cause: CategoryPageClient read the category ID directly from use(params),
 * but the GitHub Pages SPA fallback (public/404.html) stores the real ID in
 * sessionStorage.__spa_category_id and redirects to the pre-built shell at
 * /category/_/. When id === "_", parseInt("_", 10) === NaN, triggering the
 * "Invalid category." guard — no category data was ever fetched.
 *
 * Fix: Apply the same lazy useState / sessionStorage / history.replaceState
 * pattern already used in WatchPageClient and UserProfilePageClient.
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

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn() }),
}));

// ─── Mock AuthContext for SiteHeader ──────────────────────────────────────────
jest.mock("@/context/AuthContext", () => ({
  useAuth: () => ({ user: null, loading: false, signOut: jest.fn() }),
}));

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
  videos: VideoCardItem[]
): CategoryRepository {
  return {
    getAll: () => Promise.resolve(cats),
    getVideosByCategory: () => Promise.resolve(videos),
  };
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("CategoryPage — GitHub Pages SPA fallback (MYTUBE-285)", () => {
  beforeEach(() => {
    sessionStorage.clear();
    // Reset history.replaceState mock between tests
    jest.spyOn(window.history, "replaceState").mockImplementation(() => {});
  });

  afterEach(() => {
    sessionStorage.clear();
    jest.restoreAllMocks();
  });

  it("loads category using the ID stored in sessionStorage when params.id is '_' (bug reproduction)", async () => {
    // This is the bug reproduction: 404.html sets __spa_category_id = "3" and
    // redirects to /category/_/ (the pre-built shell).
    // Before the fix, id === "_" → parseInt("_", 10) === NaN → "Invalid category."
    // After the fix, CategoryPageClient reads sessionStorage and uses "3".
    sessionStorage.setItem("__spa_category_id", "3");

    const cats: Category[] = [{ id: 3, name: "Gaming" }];
    const videos = [makeVideo("v1", "Speedrun Video")];
    const repo = makeRepo(cats, videos);

    render(<CategoryPage params={makeParams("_")} repository={repo} />);

    // Must NOT show "Invalid category." error
    await waitFor(() => {
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    });

    // Must show the category heading
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Gaming" })).toBeInTheDocument();
    });

    // Must display video cards
    expect(screen.getByText("Speedrun Video")).toBeInTheDocument();
  });

  it("removes __spa_category_id from sessionStorage after reading it", async () => {
    sessionStorage.setItem("__spa_category_id", "3");

    const repo = makeRepo([{ id: 3, name: "Gaming" }], []);
    render(<CategoryPage params={makeParams("_")} repository={repo} />);

    await waitFor(() => {
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    });

    expect(sessionStorage.getItem("__spa_category_id")).toBeNull();
  });

  it("calls history.replaceState to correct the browser URL when loaded via SPA fallback", async () => {
    sessionStorage.setItem("__spa_category_id", "3");

    const replaceStateSpy = jest.spyOn(window.history, "replaceState");

    const repo = makeRepo([{ id: 3, name: "Gaming" }], []);
    render(<CategoryPage params={makeParams("_")} repository={repo} />);

    await waitFor(() => {
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    });

    // history.replaceState must have been called to correct the URL
    expect(replaceStateSpy).toHaveBeenCalled();
  });

  it("shows 'Invalid category.' when params.id is '_' and sessionStorage is empty", async () => {
    // No sessionStorage entry — fallback still shows invalid category
    const repo = makeRepo([], []);
    render(<CategoryPage params={makeParams("_")} repository={repo} />);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/invalid category/i);
    });
  });

  it("works normally with a real numeric id (non-SPA path)", async () => {
    const cats: Category[] = [{ id: 5, name: "Music" }];
    const videos = [makeVideo("v2", "Music Video")];
    const repo = makeRepo(cats, videos);

    render(<CategoryPage params={makeParams("5")} repository={repo} />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Music" })).toBeInTheDocument();
    });
    expect(screen.getByText("Music Video")).toBeInTheDocument();
  });
});
