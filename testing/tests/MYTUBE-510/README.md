# MYTUBE-510 — Library area toolbar grid: search and filter layout

## Objective
Verify the toolbar in the library area correctly aligns the search input,
category filter, and reset button.

## Preconditions
User is on the `/upload` page.

## Steps
1. Locate the `.card.toolbar` in the right-hand library area.
2. Inspect the layout of the search input and select filter.

## Expected Result
The toolbar is a CSS grid row containing the search input, category filter
select, and reset button. The elements are aligned horizontally with
consistent spacing as per the workspace layout spec.
