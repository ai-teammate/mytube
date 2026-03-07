"use client";

import React, {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  ReactNode,
} from "react";
import {
  User,
  onAuthStateChanged,
  signOut as firebaseSignOut,
} from "firebase/auth";
import { getFirebaseAuth } from "@/lib/firebase";

/** How often the heartbeat probes Firebase auth reachability (ms). */
export const HEARTBEAT_INTERVAL_MS = 30_000;

export interface AuthContextValue {
  /** The currently authenticated Firebase user, or null if not signed in. */
  user: User | null;
  /** True while Firebase is resolving the initial auth state. */
  loading: boolean;
  /** True when Firebase auth failed to initialise or returned an error. */
  authError: boolean;
  /** Returns the current Firebase ID token (auto-refreshed). */
  getIdToken: () => Promise<string | null>;
  /** Signs out the current user and clears all auth state. */
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [authError, setAuthError] = useState(false);

  useEffect(() => {
    let auth;
    try {
      auth = getFirebaseAuth();
    } catch {
      // Firebase failed to initialise (e.g. missing/invalid API key at build
      // time).  Treat the user as unauthenticated so public pages still render.
      setAuthError(true);
      setLoading(false);
      return;
    }

    const unsubscribe = onAuthStateChanged(
      auth,
      (firebaseUser) => {
        setUser(firebaseUser);
        setLoading(false);
      },
      () => {
        // Firebase auth error (e.g. auth/invalid-api-key due to missing env
        // vars at build time). Stop loading so the page can render.
        setAuthError(true);
        setLoading(false);
      }
    );

    return unsubscribe;
  }, []);

  // Mid-session reachability heartbeat: periodically force-refresh the token
  // while the user is authenticated.  The Firebase SDK v12 does NOT fire the
  // onAuthStateChanged error callback when auth domains become unreachable
  // after initialisation, so this probe is the only way to detect the failure.
  useEffect(() => {
    if (!user || authError) return;

    const probe = async () => {
      try {
        await user.getIdToken(/* forceRefresh */ true);
      } catch {
        setAuthError(true);
      }
    };

    const id = setInterval(probe, HEARTBEAT_INTERVAL_MS);
    return () => clearInterval(id);
  }, [user, authError]);

  const getIdToken = useCallback(async (): Promise<string | null> => {
    if (!user) return null;
    try {
      return await user.getIdToken();
    } catch {
      return null;
    }
  }, [user]);

  const signOut = useCallback(async (): Promise<void> => {
    const auth = getFirebaseAuth();
    await firebaseSignOut(auth);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, authError, getIdToken, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

/**
 * Returns the AuthContext value.
 * Must be called inside an <AuthProvider>.
 */
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
