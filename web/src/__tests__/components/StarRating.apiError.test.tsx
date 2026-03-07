/**
 * Unit test for MYTUBE-271: Verify that when rating API returns 500 error,
 * the stars revert to their previous state.
 *
 * This test captures the bug: when a user clicks a star and the API fails with 500,
 * the UI should display the error AND revert the stars to the actual server state.
 */
import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import StarRating from "@/components/StarRating";
import type { RatingRepository, RatingSummary } from "@/domain/rating";

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

const authedGetToken = jest.fn().mockResolvedValue("my-token");

describe("StarRating — MYTUBE-271: 500 error handling", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("reverts stars to previous state when submitRating fails with 500 error", async () => {
    // Scenario: User has already rated 3 stars.
    // They try to change it to 5 stars, but the API returns 500.
    // Expected: The UI should show 3 stars (the previous state) and an error message.

    const getSummary = jest
      .fn()
      .mockResolvedValue({
        averageRating: 3.0,
        ratingCount: 1,
        myRating: 3, // User's previous rating
      } as RatingSummary);

    const submitRating = jest.fn().mockRejectedValue(new Error("500 error"));

    const repo = makeRepo({ getSummary, submitRating });

    render(
      <StarRating
        videoID="vid-1"
        repository={repo}
        getToken={authedGetToken}
        authLoading={false}
      />
    );

    // Step 1: Wait for initial load — should show 3 stars (myRating: 3)
    await waitFor(() => {
      const buttons = screen.getAllByRole("button");
      // 3 stars should be yellow (the user's previous rating)
      // We check the first 3 buttons should have the yellow class
      expect(buttons[0]).toHaveClass("text-yellow-400");
      expect(buttons[1]).toHaveClass("text-yellow-400");
      expect(buttons[2]).toHaveClass("text-yellow-400");
      expect(buttons[3]).toHaveClass("text-gray-300");
      expect(buttons[4]).toHaveClass("text-gray-300");
    });

    // Step 2: User tries to click the 5th star (change from 3 to 5)
    const buttons = screen.getAllByRole("button");
    fireEvent.click(buttons[4]); // 5th star

    // Step 3: The API fails with 500 error
    // Expected behavior:
    //   1. An error message is displayed
    //   2. The stars revert to showing 3 (the previous myRating from the server)

    await waitFor(() => {
      // Error should be displayed
      expect(screen.getByRole("alert")).toBeInTheDocument();
      expect(screen.getByRole("alert")).toHaveTextContent(
        /could not submit rating/i
      );
    });

    // Step 4: Verify stars reverted to previous state (3 stars yellow, 2 gray)
    // Re-query buttons after error is displayed
    const updatedButtons = screen.getAllByRole("button");
    expect(updatedButtons[0]).toHaveClass("text-yellow-400");
    expect(updatedButtons[1]).toHaveClass("text-yellow-400");
    expect(updatedButtons[2]).toHaveClass("text-yellow-400");
    expect(updatedButtons[3]).toHaveClass("text-gray-300");
    expect(updatedButtons[4]).toHaveClass("text-gray-300");
  });

  it("refetches rating summary on submitRating error", async () => {
    // This test verifies that when submitRating fails,
    // getSummary is called again to refresh the rating state from the server.

    const getSummary = jest
      .fn()
      .mockResolvedValue({
        averageRating: 2.5,
        ratingCount: 2,
        myRating: 2, // User's previous rating
      } as RatingSummary);

    const submitRating = jest
      .fn()
      .mockRejectedValue(new Error("500 Internal Server Error"));

    const repo = makeRepo({ getSummary, submitRating });

    render(
      <StarRating
        videoID="vid-1"
        repository={repo}
        getToken={authedGetToken}
        authLoading={false}
      />
    );

    // Wait for initial load
    await waitFor(() => {
      expect(getSummary).toHaveBeenCalledWith("vid-1", "my-token");
    });
    const initialCallCount = (getSummary as jest.Mock).mock.calls.length;

    // User clicks a star to try to change their rating
    const buttons = screen.getAllByRole("button");
    fireEvent.click(buttons[4]); // Try to rate 5 stars

    // Wait for error and verify getSummary is called again
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
      // getSummary should be called a second time to refresh the state
      expect(getSummary).toHaveBeenCalledTimes(initialCallCount + 1);
      expect(getSummary).toHaveBeenLastCalledWith("vid-1", "my-token");
    });
  });
});
