/**
 * Unit tests for src/components/SaveToPlaylist.tsx
 */
import React from "react";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { PlaylistRepository, PlaylistSummary } from "@/domain/playlist";
import SaveToPlaylist from "@/components/SaveToPlaylist";

// ─── Helpers ─────────────────────────────────────────────────────────────────

function makePlaylist(id: string, title: string): PlaylistSummary {
  return { id, title, ownerUsername: "alice", createdAt: "2024-01-01T00:00:00Z" };
}

function makeRepo(
  playlists: PlaylistSummary[] = [],
  overrides: Partial<PlaylistRepository> = {}
): PlaylistRepository {
  return {
    getByID: jest.fn(),
    create: jest.fn().mockResolvedValue(makePlaylist("new-1", "New")),
    listMine: jest.fn().mockResolvedValue(playlists),
    listByUsername: jest.fn(),
    updateTitle: jest.fn(),
    deletePlaylist: jest.fn(),
    addVideo: jest.fn().mockResolvedValue(undefined),
    removeVideo: jest.fn(),
    ...overrides,
  };
}

function renderComponent(
  overrides: Partial<{
    playlists: PlaylistSummary[];
    repoOverrides: Partial<PlaylistRepository>;
    hidden: boolean;
  }> = {}
) {
  const { playlists = [], repoOverrides = {}, hidden = false } = overrides;
  const repo = makeRepo(playlists, repoOverrides);
  const getToken = jest.fn().mockResolvedValue("test-token");

  render(
    <SaveToPlaylist
      videoID="vid-123"
      repository={repo}
      getToken={getToken}
      hidden={hidden}
    />
  );
  return { repo, getToken };
}

// ─── Tests ───────────────────────────────────────────────────────────────────

describe("SaveToPlaylist", () => {
  beforeEach(() => jest.clearAllMocks());

  it("renders Save button by default", () => {
    renderComponent();
    expect(screen.getByRole("button", { name: /save to playlist/i })).toBeInTheDocument();
  });

  it("renders nothing when hidden=true", () => {
    const { container } = render(
      <SaveToPlaylist
        videoID="vid-1"
        repository={makeRepo()}
        getToken={jest.fn()}
        hidden={true}
      />
    );
    expect(container.firstChild).toBeNull();
  });

  it("opens dropdown on button click and loads playlists", async () => {
    const user = userEvent.setup();
    const playlists = [makePlaylist("pl-1", "Favourites")];
    const { repo } = renderComponent({ playlists });

    await user.click(screen.getByRole("button", { name: /save to playlist/i }));

    await waitFor(() => {
      expect(repo.listMine).toHaveBeenCalledWith("test-token");
    });
    expect(screen.getByRole("menu")).toBeInTheDocument();
    expect(screen.getByText("Favourites")).toBeInTheDocument();
  });

  it("shows empty state when user has no playlists", async () => {
    const user = userEvent.setup();
    renderComponent({ playlists: [] });

    await user.click(screen.getByRole("button", { name: /save to playlist/i }));

    await waitFor(() => {
      expect(screen.getByText(/no playlists yet/i)).toBeInTheDocument();
    });
  });

  it("shows error when listMine fails", async () => {
    const user = userEvent.setup();
    const repoOverrides = {
      listMine: jest.fn().mockRejectedValue(new Error("network error")),
    };
    renderComponent({ repoOverrides });

    await user.click(screen.getByRole("button", { name: /save to playlist/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/could not load playlists/i);
    });
  });

  it("shows 'New playlist' button", async () => {
    const user = userEvent.setup();
    renderComponent({ playlists: [] });

    await user.click(screen.getByRole("button", { name: /save to playlist/i }));

    await waitFor(() => {
      expect(screen.getByRole("menuitem", { name: /new playlist/i })).toBeInTheDocument();
    });
  });

  it("clicking a playlist calls addVideo", async () => {
    const user = userEvent.setup();
    const playlists = [makePlaylist("pl-1", "Favourites")];
    const { repo } = renderComponent({ playlists });

    await user.click(screen.getByRole("button", { name: /save to playlist/i }));
    await waitFor(() => screen.getByText("Favourites"));

    await act(async () => {
      await user.click(screen.getByRole("menuitem", { name: "Favourites" }));
    });

    await waitFor(() => {
      expect(repo.addVideo).toHaveBeenCalledWith("pl-1", "vid-123", "test-token");
    });
  });

  it("shows checkmark after successful save", async () => {
    const user = userEvent.setup();
    const playlists = [makePlaylist("pl-1", "Favourites")];
    renderComponent({ playlists });

    await user.click(screen.getByRole("button", { name: /save to playlist/i }));
    await waitFor(() => screen.getByText("Favourites"));

    await act(async () => {
      await user.click(screen.getByRole("menuitem", { name: "Favourites" }));
    });

    await waitFor(() => {
      expect(screen.getByLabelText("Saved")).toBeInTheDocument();
    });
  });

  it("shows inline create form when 'New playlist' is clicked", async () => {
    const user = userEvent.setup();
    renderComponent({ playlists: [] });

    await user.click(screen.getByRole("button", { name: /save to playlist/i }));
    await waitFor(() => screen.getByRole("menuitem", { name: /new playlist/i }));

    await user.click(screen.getByRole("menuitem", { name: /new playlist/i }));

    expect(screen.getByPlaceholderText(/playlist name/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^create$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^cancel$/i })).toBeInTheDocument();
  });

  it("cancelling inline create hides the form", async () => {
    const user = userEvent.setup();
    renderComponent({ playlists: [] });

    await user.click(screen.getByRole("button", { name: /save to playlist/i }));
    await waitFor(() => screen.getByRole("menuitem", { name: /new playlist/i }));

    await user.click(screen.getByRole("menuitem", { name: /new playlist/i }));
    await user.click(screen.getByRole("button", { name: /^cancel$/i }));

    expect(screen.queryByPlaceholderText(/playlist name/i)).not.toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: /new playlist/i })).toBeInTheDocument();
  });

  it("creates playlist and adds video on submit", async () => {
    const user = userEvent.setup();
    const newPlaylist = makePlaylist("new-pl", "Watch Later");
    const repoOverrides = {
      create: jest.fn().mockResolvedValue(newPlaylist),
      addVideo: jest.fn().mockResolvedValue(undefined),
    };
    renderComponent({ playlists: [], repoOverrides });

    await user.click(screen.getByRole("button", { name: /save to playlist/i }));
    await waitFor(() => screen.getByRole("menuitem", { name: /new playlist/i }));

    await user.click(screen.getByRole("menuitem", { name: /new playlist/i }));

    const input = screen.getByPlaceholderText(/playlist name/i);
    await user.type(input, "Watch Later");

    await act(async () => {
      await user.click(screen.getByRole("button", { name: /^create$/i }));
    });

    await waitFor(() => {
      expect(repoOverrides.create).toHaveBeenCalledWith("Watch Later", "test-token");
      expect(repoOverrides.addVideo).toHaveBeenCalledWith("new-pl", "vid-123", "test-token");
    });
  });

  it("shows error when addVideo fails", async () => {
    const user = userEvent.setup();
    const playlists = [makePlaylist("pl-1", "Favourites")];
    const repoOverrides = {
      addVideo: jest.fn().mockRejectedValue(new Error("forbidden")),
    };
    renderComponent({ playlists, repoOverrides });

    await user.click(screen.getByRole("button", { name: /save to playlist/i }));
    await waitFor(() => screen.getByText("Favourites"));

    await act(async () => {
      await user.click(screen.getByRole("menuitem", { name: "Favourites" }));
    });

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/failed to save/i);
    });
  });

  it("shows loading state while fetching playlists", async () => {
    const user = userEvent.setup();
    const repoOverrides = {
      listMine: jest.fn().mockReturnValue(new Promise(() => {})),
    };
    renderComponent({ repoOverrides });

    await user.click(screen.getByRole("button", { name: /save to playlist/i }));

    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });
});
