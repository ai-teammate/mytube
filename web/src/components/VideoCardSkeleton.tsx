import Skeleton from "./Skeleton";
import styles from "./VideoCard.module.css";
import skeletonStyles from "./VideoCardSkeleton.module.css";

interface VideoCardSkeletonProps {
  /** Number of skeleton cards to render. */
  count?: number;
}

/**
 * VideoCardSkeleton renders N animated placeholder cards that match the
 * VideoCard layout. Used as the loading state for video grids.
 */
export default function VideoCardSkeleton({ count = 8 }: VideoCardSkeletonProps) {
  return (
    <>
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className={styles.card} aria-hidden="true" data-testid="video-card-skeleton">
          {/* 16:9 thumbnail placeholder */}
          <div className={styles.thumb}>
            <Skeleton className={skeletonStyles.thumbFill} borderRadius="12px 12px 0 0" />
          </div>

          {/* Body placeholders */}
          <div className={styles.body}>
            {/* Title lines */}
            <Skeleton className={skeletonStyles.titleLine1} />
            <Skeleton className={skeletonStyles.titleLine2} />
            {/* Sub-line */}
            <Skeleton className={skeletonStyles.subLine} />
          </div>
        </div>
      ))}
    </>
  );
}
