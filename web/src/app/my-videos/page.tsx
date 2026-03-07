"use client";

import { Suspense } from "react";
import RequireAuth from "@/components/RequireAuth";
import {
  DashboardContent,
  defaultDashboardRepo,
  defaultManagementRepo,
  defaultPlaylistRepo,
} from "@/app/dashboard/_content";

export default function MyVideosPage() {
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
