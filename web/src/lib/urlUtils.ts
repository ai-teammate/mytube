/**
 * Validates a `next` redirect URL.
 * Must be a relative path starting with "/" and not a protocol-relative URL.
 */
export function getSafeNextUrl(next: string | null): string {
  if (!next) return "/";
  if (next.startsWith("/") && !next.startsWith("//")) return next;
  return "/";
}
