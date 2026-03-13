import Skeleton from "@/components/Skeleton";
import styles from "./WatchPageClient.module.css";
import skeletonStyles from "./WatchPageSkeleton.module.css";

/**
 * WatchPageSkeleton renders an animated placeholder for the watch page while
 * video metadata and the player are loading. Mirrors the WatchPageClient
 * layout to prevent CLS.
 */
export default function WatchPageSkeleton() {
  return (
    <div className={styles.watchLayout}>
      {/* Main content */}
      <main>
        {/* Player placeholder */}
        <div className={styles.player}>
          <Skeleton className={skeletonStyles.playerFill} borderRadius="0" />
        </div>

        {/* Title */}
        <Skeleton className={skeletonStyles.titleLine} />
        <Skeleton className={skeletonStyles.titleLineShort} />

        {/* Uploader row */}
        <div className={skeletonStyles.uploaderRow}>
          <Skeleton className={skeletonStyles.avatar} borderRadius="50%" />
          <Skeleton className={skeletonStyles.uploaderName} />
        </div>

        {/* Meta line */}
        <Skeleton className={skeletonStyles.metaLine} />

        {/* Description */}
        <Skeleton className={skeletonStyles.descBlock} />
      </main>

      {/* Sidebar */}
      <aside className={styles.sidebar}>
        <Skeleton className={skeletonStyles.sidebarBlock} />
      </aside>
    </div>
  );
}
