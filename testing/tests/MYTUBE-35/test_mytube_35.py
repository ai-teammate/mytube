"""
MYTUBE-35: Validate rating stars field — database rejects stars values outside 1-5 range.

Verifies that the CHECK constraint on the 'ratings' table restricts the 'stars'
column to values between 1 and 5 (inclusive).

Steps:
  1. Attempt to insert a record with stars = 0  → must fail (CHECK violation).
  2. Attempt to insert a record with stars = 6  → must fail (CHECK violation).
  3. Attempt to insert a record with stars = 5  → must succeed.
"""
import os
import sys
import uuid

import psycopg2.errors
import pytest

# Ensure the testing root is importable regardless of where pytest is invoked.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.components.services.ratings_service import RatingsService

# conn and db_config fixtures are provided by testing/tests/conftest.py


@pytest.fixture(scope="module")
def prerequisite_ids(conn):
    """
    Insert one user and one video so that ratings FK constraints are satisfied.
    Returns (user_id, video_id) as UUID strings.
    """
    user_id = str(uuid.uuid4())
    video_id = str(uuid.uuid4())

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO users (id, firebase_uid, username)
            VALUES (%s, %s, %s)
            """,
            (user_id, "uid_test_35", "testuser35"),
        )
        cur.execute(
            """
            INSERT INTO videos (id, uploader_id, title, status)
            VALUES (%s, %s, %s, 'ready')
            """,
            (video_id, user_id, "Test Video 35"),
        )

    return user_id, video_id


@pytest.fixture(scope="module")
def ratings_service(conn) -> RatingsService:
    """Provide a RatingsService backed by the test database connection."""
    return RatingsService(conn)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRatingsStarsConstraint:
    """CHECK (stars BETWEEN 1 AND 5) on the ratings table."""

    def test_stars_zero_rejected(self, ratings_service, prerequisite_ids):
        """Inserting stars = 0 must raise a CHECK constraint violation."""
        user_id, video_id = prerequisite_ids
        with pytest.raises(psycopg2.errors.CheckViolation):
            ratings_service.insert_rating(video_id, user_id, 0)

    def test_stars_six_rejected(self, ratings_service, prerequisite_ids):
        """Inserting stars = 6 must raise a CHECK constraint violation."""
        user_id, video_id = prerequisite_ids
        with pytest.raises(psycopg2.errors.CheckViolation):
            ratings_service.insert_rating(video_id, user_id, 6)

    def test_stars_five_accepted(self, ratings_service, prerequisite_ids):
        """Inserting stars = 5 must succeed."""
        user_id, video_id = prerequisite_ids
        ratings_service.insert_rating(video_id, user_id, 5)
        stars = ratings_service.get_rating(video_id, user_id)
        assert stars is not None, "Rating row not found after successful insert"
        assert stars == 5, f"Expected stars = 5, got {stars}"
