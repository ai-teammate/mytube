"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { Suspense } from "react";
import {
  DashboardContent,
  defaultDashboardRepo,
  defaultManagementRepo,
  defaultPlaylistRepo,
} from "./_content";

export default function DashboardPage() {
  const router = useRouter();
  const { user, loading } = useAuth();

  // Redirect unauthenticated users to login.
  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [user, loading, router]);

  // During auth loading or if user is not authenticated, don't render the dashboard.
  if (loading || !user) {
    return null;
  }

  return (
    <Suspense>
      <DashboardContent
        dashboardRepo={defaultDashboardRepo}
        managementRepo={defaultManagementRepo}
        playlistRepo={defaultPlaylistRepo}
      />
    </Suspense>
  );
}
