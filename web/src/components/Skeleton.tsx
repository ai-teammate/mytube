import styles from "./Skeleton.module.css";

interface SkeletonProps {
  /** Extra CSS classes for sizing/positioning overrides. */
  className?: string;
  width?: string;
  height?: string;
  borderRadius?: string;
}

/**
 * Skeleton renders an animated placeholder block used as a loading state.
 * Uses CSS design tokens --skeleton-base / --skeleton-highlight so it
 * automatically adapts to both light and dark themes.
 */
export default function Skeleton({
  className = "",
  width,
  height,
  borderRadius,
}: SkeletonProps) {
  return (
    <div
      aria-hidden="true"
      className={`${styles.skeleton} ${className}`}
      style={{
        ...(width ? { width } : {}),
        ...(height ? { height } : {}),
        ...(borderRadius ? { borderRadius } : {}),
      }}
    />
  );
}
