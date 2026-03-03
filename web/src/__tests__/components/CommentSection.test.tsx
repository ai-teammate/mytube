/**
 * Unit tests for src/components/CommentSection.tsx
 */
import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import CommentSection from "@/components/CommentSection";
import type { Comment, CommentRepository } from "@/domain/comment";

// ─── Mock next/image ──────────────────────────────────────────────────────────
jest.mock("next/image", () => ({
  __esModule: true,
  default: function MockImage({
    src,
    alt,
  }: {
    src: string;
    alt: string;
    [key: string]: unknown;
  }) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={src} alt={alt} />;
  },
}));

// ─── Helpers ──────────────────────────────────────────────────────────────────

function makeRepo(overrides: Partial<CommentRepository> = {}): CommentRepository {
  return {
    listByVideoID: jest.fn().mockResolvedValue([]),
    create: jest.fn().mockResolvedValue(makeComment()),
    deleteComment: jest.fn().mockResolvedValue(undefined),
    ...overrides,
  };
}

function makeComment(overrides: Partial<Comment> = {}): Comment {
  return {
    id: "c-1",
    body: "Great video!",
    author: {
      username: "alice",
      avatarUrl: null,
    },
    createdAt: "2024-01-15T10:00:00Z",
    ...overrides,
  };
}

const noOpGetToken = jest.fn().mockResolvedValue(null);
const authedGetToken = jest.fn().mockResolvedValue("my-token");

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("CommentSection", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders the Comments heading", () => {
    const repo = makeRepo();
    render(
      <CommentSection
        videoID="vid-1"
        repository={repo}
        getToken={noOpGetToken}
      />
    );
    expect(
      screen.getByRole("heading", { name: /comments/i })
    ).toBeInTheDocument();
  });

  it("shows 'No comments yet.' when the list is empty", async () => {
    const repo = makeRepo({ listByVideoID: jest.fn().mockResolvedValue([]) });
    render(
      <CommentSection
        videoID="vid-1"
        repository={repo}
        getToken={noOpGetToken}
        authLoading={false}
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/no comments yet/i)).toBeInTheDocument();
    });
  });

  it("renders loaded comments", async () => {
    const comment = makeComment({ body: "Awesome!" });
    const repo = makeRepo({
      listByVideoID: jest.fn().mockResolvedValue([comment]),
    });
    render(
      <CommentSection
        videoID="vid-1"
        repository={repo}
        getToken={noOpGetToken}
      />
    );

    await waitFor(() => {
      expect(screen.getByText("Awesome!")).toBeInTheDocument();
    });
  });

  it("renders comment author username", async () => {
    const comment = makeComment({ author: { username: "bob", avatarUrl: null } });
    const repo = makeRepo({
      listByVideoID: jest.fn().mockResolvedValue([comment]),
    });
    render(
      <CommentSection
        videoID="vid-1"
        repository={repo}
        getToken={noOpGetToken}
      />
    );

    await waitFor(() => {
      expect(screen.getByText("bob")).toBeInTheDocument();
    });
  });

  it("renders author avatar when avatarUrl is set", async () => {
    const comment = makeComment({
      author: { username: "alice", avatarUrl: "https://example.com/avatar.png" },
    });
    const repo = makeRepo({
      listByVideoID: jest.fn().mockResolvedValue([comment]),
    });
    render(
      <CommentSection
        videoID="vid-1"
        repository={repo}
        getToken={noOpGetToken}
      />
    );

    await waitFor(() => {
      const img = screen.getByAltText("alice's avatar");
      expect(img).toHaveAttribute("src", "https://example.com/avatar.png");
    });
  });

  it("renders author initials fallback when avatarUrl is null", async () => {
    const comment = makeComment({
      author: { username: "charlie", avatarUrl: null },
    });
    const repo = makeRepo({
      listByVideoID: jest.fn().mockResolvedValue([comment]),
    });
    render(
      <CommentSection
        videoID="vid-1"
        repository={repo}
        getToken={noOpGetToken}
      />
    );

    await waitFor(() => {
      expect(screen.getByLabelText("charlie's avatar")).toHaveTextContent("C");
    });
  });

  it("shows 'Login to comment' when not authenticated", async () => {
    const repo = makeRepo();
    render(
      <CommentSection
        videoID="vid-1"
        repository={repo}
        getToken={noOpGetToken}
        authLoading={false}
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/login/i)).toBeInTheDocument();
    });
  });

  it("shows comment form when authenticated", async () => {
    const repo = makeRepo();
    render(
      <CommentSection
        videoID="vid-1"
        repository={repo}
        getToken={authedGetToken}
        authLoading={false}
      />
    );

    await waitFor(() => {
      expect(
        screen.getByPlaceholderText(/add a comment/i)
      ).toBeInTheDocument();
    });
  });

  it("does not show form while authLoading", () => {
    const repo = makeRepo();
    render(
      <CommentSection
        videoID="vid-1"
        repository={repo}
        getToken={authedGetToken}
        authLoading={true}
      />
    );

    expect(screen.queryByPlaceholderText(/add a comment/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/login/i)).not.toBeInTheDocument();
  });

  it("calls create and adds new comment on submit", async () => {
    const newComment = makeComment({ body: "New comment!" });
    const create = jest.fn().mockResolvedValue(newComment);
    const repo = makeRepo({ create });
    render(
      <CommentSection
        videoID="vid-1"
        repository={repo}
        getToken={authedGetToken}
        authLoading={false}
      />
    );

    await waitFor(() => {
      expect(
        screen.getByPlaceholderText(/add a comment/i)
      ).toBeInTheDocument();
    });

    const textarea = screen.getByLabelText(/comment body/i);
    fireEvent.change(textarea, { target: { value: "New comment!" } });

    const button = screen.getByRole("button", { name: /comment/i });
    fireEvent.click(button);

    await waitFor(() => {
      expect(create).toHaveBeenCalledWith("vid-1", "New comment!", "my-token");
    });

    await waitFor(() => {
      expect(screen.getByText("New comment!")).toBeInTheDocument();
    });
  });

  it("shows error when create fails", async () => {
    const create = jest.fn().mockRejectedValue(new Error("failed"));
    const repo = makeRepo({ create });
    render(
      <CommentSection
        videoID="vid-1"
        repository={repo}
        getToken={authedGetToken}
        authLoading={false}
      />
    );

    await waitFor(() =>
      screen.getByPlaceholderText(/add a comment/i)
    );

    const textarea = screen.getByLabelText(/comment body/i);
    fireEvent.change(textarea, { target: { value: "hello" } });
    fireEvent.click(screen.getByRole("button", { name: /comment/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        /could not post comment/i
      );
    });
  });

  it("shows load error when listByVideoID fails", async () => {
    const repo = makeRepo({
      listByVideoID: jest.fn().mockRejectedValue(new Error("fetch failed")),
    });
    render(
      <CommentSection
        videoID="vid-1"
        repository={repo}
        getToken={noOpGetToken}
      />
    );

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        /could not load comments/i
      );
    });
  });

  it("submit button is disabled when textarea is empty", async () => {
    const repo = makeRepo();
    render(
      <CommentSection
        videoID="vid-1"
        repository={repo}
        getToken={authedGetToken}
        authLoading={false}
      />
    );

    await waitFor(() =>
      screen.getByPlaceholderText(/add a comment/i)
    );

    const button = screen.getByRole("button", { name: /comment/i });
    expect(button).toBeDisabled();
  });

  it("clears textarea after successful submit", async () => {
    const repo = makeRepo({
      create: jest.fn().mockResolvedValue(makeComment()),
    });
    render(
      <CommentSection
        videoID="vid-1"
        repository={repo}
        getToken={authedGetToken}
        authLoading={false}
      />
    );

    await waitFor(() =>
      screen.getByPlaceholderText(/add a comment/i)
    );

    const textarea = screen.getByLabelText(/comment body/i);
    fireEvent.change(textarea, { target: { value: "hello" } });
    fireEvent.click(screen.getByRole("button", { name: /comment/i }));

    await waitFor(() => {
      expect((textarea as HTMLTextAreaElement).value).toBe("");
    });
  });

  it("calls listByVideoID with the videoID on mount", async () => {
    const listByVideoID = jest.fn().mockResolvedValue([]);
    const repo = makeRepo({ listByVideoID });
    render(
      <CommentSection
        videoID="my-video-id"
        repository={repo}
        getToken={noOpGetToken}
      />
    );

    await waitFor(() => {
      expect(listByVideoID).toHaveBeenCalledWith("my-video-id");
    });
  });
});
