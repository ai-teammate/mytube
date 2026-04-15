"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import RequireAuth from "@/components/RequireAuth";
import AvatarPreview from "@/components/AvatarPreview";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

interface ProfileData {
  username: string;
  avatarUrl: string;
}

export default function SettingsPage() {
  return (
    <RequireAuth>
      <SettingsPageContent />
    </RequireAuth>
  );
}

function SettingsPageContent() {
  const router = useRouter();
  const { user, getIdToken, signOut } = useAuth();

  const [form, setForm] = useState<ProfileData>({ username: "", avatarUrl: "" });
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Fetch current profile once authenticated.
  useEffect(() => {
    if (!user) return;

    async function fetchProfile() {
      const token = await getIdToken();
      if (!token) return;

      try {
        const res = await fetch(`${API_URL}/api/me`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          const data = await res.json();
          setForm({
            username: data.username ?? "",
            avatarUrl: data.avatar_url ?? "",
          });
        }
      } catch {
        // Profile fetch failure is non-fatal; form will start empty.
        setSaveError("Could not load your current profile. You can still update your settings.");
      }
    }

    fetchProfile();
  }, [user, getIdToken]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaveError(null);
    setSaveSuccess(false);
    setSubmitting(true);

    try {
      const token = await getIdToken();
      if (!token) {
        setSaveError("You are not authenticated. Please sign in again.");
        setSubmitting(false);
        return;
      }

      const res = await fetch(`${API_URL}/api/me`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          username: form.username,
          avatar_url: form.avatarUrl || null,
        }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setSaveError(body.error ?? "Failed to save settings. Please try again.");
        return;
      }

      setSaveSuccess(true);
    } catch {
      setSaveError("Network error. Please check your connection and try again.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleSignOut() {
    await signOut();
    router.replace("/login");
  }


  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-md p-8 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Account settings</h1>
            <p className="mt-1 text-sm text-gray-500">{user?.email}</p>
          </div>
          <button
            type="button"
            onClick={handleSignOut}
            className="text-sm text-red-600 hover:underline"
          >
            Sign out
          </button>
        </div>

        {saveError && (
          <div
            role="alert"
            className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700"
          >
            {saveError}
          </div>
        )}

        {saveSuccess && (
          <div
            role="status"
            className="rounded-lg bg-green-50 border border-green-200 px-4 py-3 text-sm text-green-700"
          >
            Settings saved successfully.
          </div>
        )}

        <form onSubmit={handleSave} className="space-y-4">
          <div>
            <label
              htmlFor="username"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Username
            </label>
            <input
              id="username"
              type="text"
              required
              value={form.username}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, username: e.target.value }))
              }
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="Your username"
            />
          </div>

          <div>
            <label
              htmlFor="avatar_url"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Avatar URL
            </label>
            <input
              id="avatar_url"
              type="url"
              value={form.avatarUrl}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, avatarUrl: e.target.value }))
              }
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="https://example.com/avatar.png"
            />
            <p className="mt-1 text-xs text-gray-400">
              Enter a URL to a profile image
            </p>
            {form.avatarUrl && (
              <div className="mt-3">
                <AvatarPreview src={form.avatarUrl} />
              </div>
            )}
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {submitting ? "Saving…" : "Save settings"}
          </button>
        </form>
      </div>
    </div>
  );
}
