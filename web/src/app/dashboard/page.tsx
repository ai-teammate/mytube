"use client";

import { Suspense } from "react";
import RequireAuth from "@/components/RequireAuth";
import {
  DashboardContent,
  defaultDashboardRepo,
  defaultManagementRepo,
  defaultPlaylistRepo,
} from "./_content";

export default function DashboardPage() {
  return (
    <RequireAuth>
      <Suspense>
        <DashboardContent
          dashboardRepo={defaultDashboardRepo}
          managementRepo={defaultManagementRepo}
          playlistRepo={defaultPlaylistRepo}
        />
      </Suspense>
    </RequireAuth>
  );
}
