/**
 * Unit tests for src/context/ThemeContext.tsx
 */
import React from "react";
import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ThemeProvider, useTheme } from "@/context/ThemeContext";

// ─── localStorage mock ────────────────────────────────────────────────────────

const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: jest.fn((key: string) => store[key] ?? null),
    setItem: jest.fn((key: string, value: string) => { store[key] = value; }),
    removeItem: jest.fn((key: string) => { delete store[key]; }),
    clear: jest.fn(() => { store = {}; }),
  };
})();

Object.defineProperty(window, "localStorage", { value: localStorageMock });

// ─── Test helpers ─────────────────────────────────────────────────────────────

/** Consumer component that exposes theme state via data-testid attributes */
function ThemeConsumer() {
  const { theme, toggleTheme } = useTheme();
  return (
    <div>
      <span data-testid="theme">{theme}</span>
      <button data-testid="toggle-btn" onClick={toggleTheme}>
        Toggle
      </button>
    </div>
  );
}

function renderWithProvider(stored?: string) {
  if (stored !== undefined) {
    localStorageMock.getItem.mockReturnValueOnce(stored);
  }
  return render(
    <ThemeProvider>
      <ThemeConsumer />
    </ThemeProvider>
  );
}

beforeEach(() => {
  jest.clearAllMocks();
  localStorageMock.clear();
  // Reset data-theme attribute
  document.body.removeAttribute("data-theme");
});

// ─── ThemeProvider ────────────────────────────────────────────────────────────

describe("ThemeProvider", () => {
  it("defaults to light theme when no localStorage value", () => {
    renderWithProvider();
    // Initial render shows "light" before useEffect runs
    expect(screen.getByTestId("theme").textContent).toBe("light");
  });

  it("applies 'light' data-theme on document.body on mount (no stored value)", async () => {
    renderWithProvider();
    await act(async () => {});
    expect(document.body.getAttribute("data-theme")).toBe("light");
  });

  it("reads 'dark' from localStorage and applies it on mount", async () => {
    localStorageMock.getItem.mockReturnValueOnce("dark");
    render(
      <ThemeProvider>
        <ThemeConsumer />
      </ThemeProvider>
    );
    await act(async () => {});
    expect(screen.getByTestId("theme").textContent).toBe("dark");
    expect(document.body.getAttribute("data-theme")).toBe("dark");
  });

  it("treats an unrecognised localStorage value as light", async () => {
    localStorageMock.getItem.mockReturnValueOnce("blue");
    render(
      <ThemeProvider>
        <ThemeConsumer />
      </ThemeProvider>
    );
    await act(async () => {});
    expect(screen.getByTestId("theme").textContent).toBe("light");
    expect(document.body.getAttribute("data-theme")).toBe("light");
  });

  it("treats a null localStorage value as light", async () => {
    localStorageMock.getItem.mockReturnValueOnce(null);
    render(
      <ThemeProvider>
        <ThemeConsumer />
      </ThemeProvider>
    );
    await act(async () => {});
    expect(screen.getByTestId("theme").textContent).toBe("light");
  });

  it("reads from localStorage using the key 'theme'", async () => {
    renderWithProvider();
    await act(async () => {});
    expect(localStorageMock.getItem).toHaveBeenCalledWith("theme");
  });
});

// ─── toggleTheme ──────────────────────────────────────────────────────────────

describe("toggleTheme", () => {
  it("switches from light to dark on toggle", async () => {
    const user = userEvent.setup();
    renderWithProvider();
    await act(async () => {});

    await user.click(screen.getByTestId("toggle-btn"));
    expect(screen.getByTestId("theme").textContent).toBe("dark");
  });

  it("switches from dark to light on toggle", async () => {
    const user = userEvent.setup();
    localStorageMock.getItem.mockReturnValueOnce("dark");
    render(
      <ThemeProvider>
        <ThemeConsumer />
      </ThemeProvider>
    );
    await act(async () => {});

    await user.click(screen.getByTestId("toggle-btn"));
    expect(screen.getByTestId("theme").textContent).toBe("light");
  });

  it("persists the new theme to localStorage on toggle", async () => {
    const user = userEvent.setup();
    renderWithProvider();
    await act(async () => {});

    await user.click(screen.getByTestId("toggle-btn"));
    expect(localStorageMock.setItem).toHaveBeenCalledWith("theme", "dark");
  });

  it("updates data-theme on document.body to 'dark' on toggle", async () => {
    const user = userEvent.setup();
    renderWithProvider();
    await act(async () => {});

    await user.click(screen.getByTestId("toggle-btn"));
    expect(document.body.getAttribute("data-theme")).toBe("dark");
  });

  it("updates data-theme on document.body back to 'light' on second toggle", async () => {
    const user = userEvent.setup();
    renderWithProvider();
    await act(async () => {});

    await user.click(screen.getByTestId("toggle-btn")); // → dark
    await user.click(screen.getByTestId("toggle-btn")); // → light
    expect(document.body.getAttribute("data-theme")).toBe("light");
  });

  it("persists 'light' to localStorage when toggling back from dark", async () => {
    const user = userEvent.setup();
    localStorageMock.getItem.mockReturnValueOnce("dark");
    render(
      <ThemeProvider>
        <ThemeConsumer />
      </ThemeProvider>
    );
    await act(async () => {});

    await user.click(screen.getByTestId("toggle-btn"));
    expect(localStorageMock.setItem).toHaveBeenCalledWith("theme", "light");
  });
});

// ─── useTheme ─────────────────────────────────────────────────────────────────

describe("useTheme", () => {
  it("throws when used outside ThemeProvider", () => {
    // Suppress console.error for this test
    const consoleError = jest.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<ThemeConsumer />)).toThrow(
      "useTheme must be used within a ThemeProvider"
    );
    consoleError.mockRestore();
  });

  it("returns theme and toggleTheme from ThemeProvider", async () => {
    renderWithProvider();
    await act(async () => {});
    expect(screen.getByTestId("theme")).toBeInTheDocument();
    expect(screen.getByTestId("toggle-btn")).toBeInTheDocument();
  });
});
