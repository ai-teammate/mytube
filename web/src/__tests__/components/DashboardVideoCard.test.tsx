/**
 * Unit tests for src/components/DashboardVideoCard.tsx
 */
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import DashboardVideoCard from "@/components/DashboardVideoCard";
import type { DashboardVideo } from "@/domain/dashboard";

// ─── Mock next/image ──────────────────────────────────────────────────────────

jest.mock("next/image", () => ({
  __esModule: true,
  default: ({
    src,
    alt,
    fill: _fill,
    className,
  }: {
    src: string;
    alt: string;
    fill?: boolean;
    className?: string;
  }) => (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={src} alt={alt} className={className} />
  ),
}));

// ─── Helpers ──────────────────────────────────────────────────────────────────

function makeVideo(overrides: Partial<DashboardVideo> = {}): DashboardVideo {
  return {
    id: "vid-1",
    title: "Test Video",
    status: "ready",
    thumbnailUrl: "https://cdn.example.com/thumb.jpg",
    viewCount: 42,
    createdAt: "2024-01-15T10:00:00Z",
    description: null,
    categoryId: null,
    tags: [],
    ...overrides,
  };
}

function renderCard(
  video: DashboardVideo = makeVideo(),
  props: Partial<Parameters<typeof DashboardVideoCard>[0]> = {}
) {
  const onEdit = jest.fn();
  const onDelete = jest.fn();
  const onConfirmDelete = jest.fn();
  const onCancelDelete = jest.fn();

  const { rerender } = render(
    <DashboardVideoCard
      video={video}
      onEdit={onEdit}
      onDelete={onDelete}
      isDeleting={false}
      isConfirmingDelete={false}
      onConfirmDelete={onConfirmDelete}
      onCancelDelete={onCancelDelete}
      {...props}
    />
  );

  return { onEdit, onDelete, onConfirmDelete, onCancelDelete, rerender };
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("DashboardVideoCard", () => {
  // ─── Thumbnail ────────────────────────────────────────────────────────────

  it("renders thumbnail image when thumbnailUrl is provided", () => {
    renderCard(makeVideo({ thumbnailUrl: "https://cdn.example.com/thumb.jpg" }));
    const img = screen.getByAltText("Test Video thumbnail");
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute("src", "https://cdn.example.com/thumb.jpg");
  });

  it("renders placeholder when thumbnailUrl is null", () => {
    renderCard(makeVideo({ thumbnailUrl: null }));
    expect(screen.getByText("No thumbnail")).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  // ─── Title ────────────────────────────────────────────────────────────────

  it("renders title as a link to watch page for ready videos", () => {
    renderCard(makeVideo({ id: "vid-42", title: "Ready Video", status: "ready" }));
    const link = screen.getByRole("link", { name: "Ready Video" });
    expect(link).toHaveAttribute("href", "/v/vid-42");
  });

  it("renders title as plain text for processing videos", () => {
    renderCard(makeVideo({ title: "Processing Video", status: "processing" }));
    expect(screen.getByText("Processing Video")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Processing Video" })).not.toBeInTheDocument();
  });

  it("renders title as plain text for pending videos", () => {
    renderCard(makeVideo({ title: "Pending Video", status: "pending" }));
    expect(screen.getByText("Pending Video")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Pending Video" })).not.toBeInTheDocument();
  });

  it("renders title as plain text for failed videos", () => {
    renderCard(makeVideo({ title: "Failed Video", status: "failed" }));
    expect(screen.getByText("Failed Video")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Failed Video" })).not.toBeInTheDocument();
  });

  // ─── Status badge ─────────────────────────────────────────────────────────

  it("renders Ready status badge for ready video", () => {
    renderCard(makeVideo({ status: "ready" }));
    expect(screen.getByText("Ready")).toBeInTheDocument();
  });

  it("renders Processing status badge for processing video", () => {
    renderCard(makeVideo({ status: "processing" }));
    expect(screen.getByText("Processing")).toBeInTheDocument();
  });

  it("renders Pending status badge for pending video", () => {
    renderCard(makeVideo({ status: "pending" }));
    expect(screen.getByText("Pending")).toBeInTheDocument();
  });

  it("renders Failed status badge for failed video", () => {
    renderCard(makeVideo({ status: "failed" }));
    expect(screen.getByText("Failed")).toBeInTheDocument();
  });

  // ─── Meta (view count + date) ─────────────────────────────────────────────

  it("renders formatted view count", () => {
    renderCard(makeVideo({ viewCount: 1234567 }));
    expect(screen.getByText(/1,234,567 views/)).toBeInTheDocument();
  });

  it("renders view count for zero views", () => {
    renderCard(makeVideo({ viewCount: 0 }));
    expect(screen.getByText(/0 views/)).toBeInTheDocument();
  });

  it("renders creation date", () => {
    renderCard(makeVideo({ createdAt: "2024-06-01T00:00:00Z" }));
    // Presence of a date string (format varies by locale — just check it renders)
    expect(screen.getByText(/2024/)).toBeInTheDocument();
  });

  // ─── Edit action ──────────────────────────────────────────────────────────

  it("renders Edit button with accessible label", () => {
    renderCard(makeVideo({ title: "My Video" }));
    expect(screen.getByRole("button", { name: /edit my video/i })).toBeInTheDocument();
  });

  it("calls onEdit with the video when Edit is clicked", () => {
    const video = makeVideo({ title: "My Video" });
    const { onEdit } = renderCard(video);
    fireEvent.click(screen.getByRole("button", { name: /edit my video/i }));
    expect(onEdit).toHaveBeenCalledTimes(1);
    expect(onEdit).toHaveBeenCalledWith(video);
  });

  // ─── Delete action (normal state) ─────────────────────────────────────────

  it("renders Delete button with accessible label when not confirming", () => {
    renderCard(makeVideo({ title: "My Video" }));
    expect(screen.getByRole("button", { name: /delete my video/i })).toBeInTheDocument();
  });

  it("calls onDelete with the video id when Delete is clicked", () => {
    const video = makeVideo({ id: "vid-99", title: "My Video" });
    const { onDelete } = renderCard(video);
    fireEvent.click(screen.getByRole("button", { name: /delete my video/i }));
    expect(onDelete).toHaveBeenCalledTimes(1);
    expect(onDelete).toHaveBeenCalledWith("vid-99");
  });

  // ─── Delete confirmation state ────────────────────────────────────────────

  it("shows Confirm and Cancel buttons when isConfirmingDelete is true", () => {
    renderCard(makeVideo(), { isConfirmingDelete: true });
    expect(screen.getByRole("button", { name: /confirm/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /cancel/i })).toBeInTheDocument();
  });

  it("does not show Delete button when isConfirmingDelete is true", () => {
    renderCard(makeVideo({ title: "My Video" }), { isConfirmingDelete: true });
    expect(screen.queryByRole("button", { name: /delete my video/i })).not.toBeInTheDocument();
  });

  it("calls onConfirmDelete when Confirm is clicked", () => {
    const { onConfirmDelete } = renderCard(makeVideo(), { isConfirmingDelete: true });
    fireEvent.click(screen.getByRole("button", { name: /confirm/i }));
    expect(onConfirmDelete).toHaveBeenCalledTimes(1);
  });

  it("calls onCancelDelete when Cancel is clicked", () => {
    const { onCancelDelete } = renderCard(makeVideo(), { isConfirmingDelete: true });
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onCancelDelete).toHaveBeenCalledTimes(1);
  });

  // ─── Deleting (in-progress) state ─────────────────────────────────────────

  it("shows 'Deleting…' text when isDeleting and isConfirmingDelete are true", () => {
    renderCard(makeVideo(), { isConfirmingDelete: true, isDeleting: true });
    expect(screen.getByRole("button", { name: /deleting/i })).toBeInTheDocument();
  });

  it("disables Confirm button while isDeleting is true", () => {
    renderCard(makeVideo(), { isConfirmingDelete: true, isDeleting: true });
    expect(screen.getByRole("button", { name: /deleting/i })).toBeDisabled();
  });

  it("disables Cancel button while isDeleting is true", () => {
    renderCard(makeVideo(), { isConfirmingDelete: true, isDeleting: true });
    expect(screen.getByRole("button", { name: /cancel/i })).toBeDisabled();
  });
});
