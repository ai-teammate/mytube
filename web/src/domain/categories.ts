// Domain layer: category definitions, kept in sync with the DB seed data.
// Centralising them here prevents hard-coded IDs from spreading into UI components.

export const CATEGORIES = [
  { id: 1, label: "Education" },
  { id: 2, label: "Entertainment" },
  { id: 3, label: "Gaming" },
  { id: 4, label: "Music" },
  { id: 5, label: "Other" },
] as const;

export type CategoryId = (typeof CATEGORIES)[number]["id"];
