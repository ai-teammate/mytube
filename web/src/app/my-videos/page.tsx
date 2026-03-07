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
      {/* Inner Suspense: satisfies Next.js static-export requirement for
          useSearchParams() called inside DashboardContent */}
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
