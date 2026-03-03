import { Suspense } from "react";
import {
  DashboardContent,
  defaultDashboardRepo,
  defaultManagementRepo,
} from "./_content";

export default function DashboardPage() {
  return (
    <Suspense>
      <DashboardContent
        dashboardRepo={defaultDashboardRepo}
        managementRepo={defaultManagementRepo}
      />
    </Suspense>
  );
}
