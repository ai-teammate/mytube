/**
 * Unit tests for src/app/search/page.tsx
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import type { VideoCardItem, SearchRepository } from "@/domain/search";

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

// ─── Mock next/navigation ─────────────────────────────────────────────────────
const mockGet = jest.fn();
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn() }),
  useSearchParams: () => ({
    get: mockGet,
  }),
}));

// ─── Mock AuthContext for SiteHeader ──────────────────────────────────────────
jest.mock("@/context/AuthContext", () => ({
  useAuth: () => ({ user: null, loading: false, signOut: jest.fn() }),
}));

// ─── Import page AFTER mocks ──────────────────────────────────────────────────
import SearchPage from "@/app/search/SearchPageClient";

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
  impl: (q: string) => Promise<VideoCardItem[]>
): SearchRepository {
  return {
    search: (query) => impl(query),
  };
}

beforeEach(() => {
  jest.clearAllMocks();
  // Default: no query
  mockGet.mockReturnValue(null);
});

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("SearchPage", () => {
  it("shows skeleton loading state initially", () => {
    const repo = makeRepo(() => new Promise(() => {}));

    render(<SearchPage repository={repo} />);

    expect(screen.getAllByTestId("video-card-skeleton").length).toBeGreaterThan(0);
  });

  it("shows 'No videos found' when results are empty", async () => {
    mockGet.mockReturnValue("nothing");
    const repo = makeRepo(() => Promise.resolve([]));

    render(<SearchPage repository={repo} />);

    await waitFor(() => {
      expect(screen.getByText(/no videos found/i)).toBeInTheDocument();
    });
  });

  it("renders video cards when results are returned", async () => {
    mockGet.mockReturnValue("go");
    const repo = makeRepo(() =>
      Promise.resolve([
        makeVideo("v1", "Go Tutorial"),
        makeVideo("v2", "Go Advanced"),
      ])
    );

    render(<SearchPage repository={repo} />);

    await waitFor(() => {
      expect(screen.getByText("Go Tutorial")).toBeInTheDocument();
      expect(screen.getByText("Go Advanced")).toBeInTheDocument();
    });
  });

  it("shows error message when repository throws", async () => {
    mockGet.mockReturnValue("test");
    const repo = makeRepo(() => Promise.reject(new Error("network error")));

    render(<SearchPage repository={repo} />);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        /could not load search results/i
      );
    });
  });

  it("displays the search query in the heading", async () => {
    mockGet.mockReturnValue("go tutorial");
    const repo = makeRepo(() => Promise.resolve([]));

    render(<SearchPage repository={repo} />);

    await waitFor(() => {
      expect(
        screen.getByText(/go tutorial/i)
      ).toBeInTheDocument();
    });
  });

  it("shows 'Search' heading when no query is provided", async () => {
    mockGet.mockReturnValue(null);
    const repo = makeRepo(() => Promise.resolve([]));

    render(<SearchPage repository={repo} />);

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: /^search$/i })
      ).toBeInTheDocument();
    });
  });

  it("calls search with the query from URL", async () => {
    mockGet.mockReturnValue("python");
    const searchFn = jest.fn<Promise<VideoCardItem[]>, [string]>(() =>
      Promise.resolve([])
    );
    const repo: SearchRepository = { search: searchFn };

    render(<SearchPage repository={repo} />);

    await waitFor(() => {
      expect(searchFn).toHaveBeenCalledWith("python", undefined, 20, 0);
    });
  });
});
