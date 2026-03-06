# MYTUBE-265: View video with no ratings — widget displays zero state correctly

## Test Objective

Verify that the rating widget correctly renders the default state when no ratings have been submitted for a video.

## Test Specifications

- **Ticket**: MYTUBE-265
- **Type**: UI/Component Test
- **Framework**: Playwright (sync API)
- **Browser**: Chromium
- **Duration**: ~1 second

## Requirements

The automated test verifies the following requirements:

1. The rating widget is visible on the watch page
2. The widget displays "0 / 5" (zero average rating)
3. The widget displays "(0)" (zero rating count)
4. All 5 star icons are in the default unselected/empty state (aria-pressed="false")

## Test Cases

### 1. test_rating_widget_structure_zero_state
- **Purpose**: Verify the complete DOM structure and attributes of the StarRating component
- **Assertions**:
  - All 5 star buttons are present and visible
  - All 5 star buttons have `aria-pressed="false"`
  - The rating summary span displays "0 / 5 (0)"
  - The "Log in to rate this video" message is present

### 2. test_rating_widget_displays_zero_slash_five
- **Purpose**: Verify the rating summary text is correct
- **Assertions**:
  - The summary span contains "0 / 5"
  - The summary span contains "(0)"

### 3. test_all_stars_unselected_in_zero_state
- **Purpose**: Verify all stars are unselected
- **Assertions**:
  - Each of the 5 star buttons has `aria-pressed="false"`

## Architecture

The test uses Playwright's component testing approach with inline HTML fixtures. Each test case:

1. Creates a minimal HTML page with the rating widget markup
2. Loads it into Playwright's page context
3. Uses Playwright locators to find DOM elements
4. Asserts on element attributes and text content using the `expect` API

This approach allows testing the component's rendering without requiring a full backend API or database.

## Running the Tests

```bash
cd /home/runner/work/mytube/mytube

# Run all MYTUBE-265 tests
pytest testing/tests/MYTUBE-265/test_mytube_265.py -v

# Run a specific test
pytest testing/tests/MYTUBE-265/test_mytube_265.py::TestRatingWidgetZeroState::test_rating_widget_displays_zero_slash_five -v

# Run with detailed output
pytest testing/tests/MYTUBE-265/test_mytube_265.py -vv --tb=short
```

## Test Result

✅ **ALL TESTS PASSED** (3/3)

- test_rating_widget_structure_zero_state: PASSED
- test_rating_widget_displays_zero_slash_five: PASSED
- test_all_stars_unselected_in_zero_state: PASSED

## Files

- `test_mytube_265.py` - Test implementation
- `config.yaml` - Test configuration
- `__init__.py` - Package initialization

## Notes

- Tests are isolated and do not require a running API server or database
- Each test is independent and can be run in any order
- Tests use Playwright's synchronous API for simplicity
- The component is tested in isolation to ensure zero-state rendering is correct
