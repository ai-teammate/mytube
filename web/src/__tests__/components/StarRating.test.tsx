/**
 * Unit tests for src/components/StarRating.tsx
 */
import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import StarRating from "@/components/StarRating";
import type { RatingRepository, RatingSummary } from "@/domain/rating";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function makeRepo(overrides: Partial<RatingRepository> = {}): RatingRepository {
  return {
    getSummary: jest.fn().mockResolvedValue({
      averageRating: 0,
      ratingCount: 0,
      myRating: null,
    } as RatingSummary),
    submitRating: jest.fn().mockResolvedValue({
      averageRating: 0,
      ratingCount: 0,
      myRating: null,
    } as RatingSummary),
    ...overrides,
  };
}

const noOpGetToken = jest.fn().mockResolvedValue(null);
const authedGetToken = jest.fn().mockResolvedValue("my-token");

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("StarRating", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders 5 star buttons", () => {
    const repo = makeRepo();
    render(
      <StarRating
        videoID="vid-1"
        repository={repo}
        getToken={noOpGetToken}
      />
    );
    const buttons = screen.getAllByRole("button");
    expect(buttons).toHaveLength(5);
  });

  it("shows average rating and count after loading", async () => {
    const repo = makeRepo({
      getSummary: jest.fn().mockResolvedValue({
        averageRating: 4.2,
        ratingCount: 10,
        myRating: null,
      }),
    });
    render(
      <StarRating
        videoID="vid-1"
        repository={repo}
        getToken={noOpGetToken}
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/4\.2 \/ 5 \(10\)/)).toBeInTheDocument();
    });
  });

  it("shows 'No ratings yet' when count is 0", async () => {
    const repo = makeRepo({
      getSummary: jest.fn().mockResolvedValue({
        averageRating: 0,
        ratingCount: 0,
        myRating: null,
      }),
    });
    render(
      <StarRating
        videoID="vid-1"
        repository={repo}
        getToken={noOpGetToken}
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/no ratings yet/i)).toBeInTheDocument();
    });
  });

  it("shows login prompt when not authenticated (token is null)", async () => {
    const repo = makeRepo();
    render(
      <StarRating
        videoID="vid-1"
        repository={repo}
        getToken={noOpGetToken}
        authLoading={false}
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/log in/i)).toBeInTheDocument();
    });
  });

  it("does not show login prompt when authLoading is true", () => {
    const repo = makeRepo();
    render(
      <StarRating
        videoID="vid-1"
        repository={repo}
        getToken={noOpGetToken}
        authLoading={true}
      />
    );

    expect(screen.queryByText(/log in/i)).not.toBeInTheDocument();
  });

  it("calls submitRating when a star is clicked with token", async () => {
    const submitRating = jest.fn().mockResolvedValue({
      averageRating: 3.0,
      ratingCount: 1,
      myRating: 3,
    });
    const repo = makeRepo({ submitRating });
    render(
      <StarRating
        videoID="vid-1"
        repository={repo}
        getToken={authedGetToken}
        authLoading={false}
      />
    );

    const buttons = screen.getAllByRole("button");
    fireEvent.click(buttons[2]); // 3rd star = 3 stars

    await waitFor(() => {
      expect(submitRating).toHaveBeenCalledWith("vid-1", 3, "my-token");
    });
  });

  it("shows error when submitRating fails", async () => {
    const submitRating = jest.fn().mockRejectedValue(new Error("failed"));
    const repo = makeRepo({ submitRating });
    render(
      <StarRating
        videoID="vid-1"
        repository={repo}
        getToken={authedGetToken}
        authLoading={false}
      />
    );

    const buttons = screen.getAllByRole("button");
    fireEvent.click(buttons[0]);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
      expect(screen.getByRole("alert")).toHaveTextContent(
        /could not submit rating/i
      );
    });
  });

  it("shows 'Log in to rate' error when no token on submit", async () => {
    const submitRating = jest.fn();
    const repo = makeRepo({ submitRating });
    const getTokenNoAuth = jest.fn().mockResolvedValue(null);
    render(
      <StarRating
        videoID="vid-1"
        repository={repo}
        getToken={getTokenNoAuth}
        authLoading={false}
      />
    );

    const buttons = screen.getAllByRole("button");
    fireEvent.click(buttons[0]);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        /please log in/i
      );
    });
    expect(submitRating).not.toHaveBeenCalled();
  });

  it("calls getSummary with the videoID on mount", async () => {
    const getSummary = jest.fn().mockResolvedValue({
      averageRating: 0,
      ratingCount: 0,
      myRating: null,
    });
    const repo = makeRepo({ getSummary });
    render(
      <StarRating
        videoID="vid-42"
        repository={repo}
        getToken={noOpGetToken}
      />
    );

    await waitFor(() => {
      expect(getSummary).toHaveBeenCalledWith("vid-42", null);
    });
  });

  it("shows count in parentheses when count is 1", async () => {
    const repo = makeRepo({
      getSummary: jest.fn().mockResolvedValue({
        averageRating: 5.0,
        ratingCount: 1,
        myRating: 5,
      }),
    });
    render(
      <StarRating
        videoID="vid-1"
        repository={repo}
        getToken={noOpGetToken}
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/5\.0 \/ 5 \(1\)/)).toBeInTheDocument();
    });
  });

  it("displays vote count as plain number in parentheses without a label", async () => {
    const repo = makeRepo({
      getSummary: jest.fn().mockResolvedValue({
        averageRating: 4.2,
        ratingCount: 10,
        myRating: null,
      }),
    });
    render(
      <StarRating
        videoID="vid-1"
        repository={repo}
        getToken={noOpGetToken}
      />
    );

    await waitFor(() => {
      // Expected format: "4.2 / 5 (10)" — the closing paren must follow the number immediately.
      expect(screen.getByText(/4\.2 \/ 5 \(10\)/)).toBeInTheDocument();
    });
  });

  it("updates summary after successful submitRating", async () => {
    const submitRating = jest.fn().mockResolvedValue({
      averageRating: 4.0,
      ratingCount: 5,
      myRating: 4,
    });
    const repo = makeRepo({ submitRating });
    render(
      <StarRating
        videoID="vid-1"
        repository={repo}
        getToken={authedGetToken}
        authLoading={false}
      />
    );

    const buttons = screen.getAllByRole("button");
    fireEvent.click(buttons[3]); // 4th star

    await waitFor(() => {
      expect(screen.getByText(/4\.0 \/ 5 \(5\)/)).toBeInTheDocument();
    });
  });
});
