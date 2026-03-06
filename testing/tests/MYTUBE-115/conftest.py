"""
Presetup for MYTUBE-115 test suite.

Creates a stable test user (tester) and a ready video before the Playwright
tests run. This ensures the public user profile page has data to display.

Teardown removes the user and all their owned rows via _cleanup_users so
other test data in the database is not affected.
"""
from __future__ import annotations

import os
import sys
import uuid

import psycopg2
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.db_config import DBConfig
from testing.tests.conftest import _cleanup_users

_TEST_USERNAME = "tester"
_TEST_FIREBASE_UID = "firebase_uid_mytube115"
_THUMB_TEMPLATE = "https://storage.googleapis.com/mytube-hls-output/videos/{vid}/thumbnail.jpg"


@pytest.fixture(scope="module", autouse=True)
def setup_test_user_and_video() -> None:
    """Insert a test user 'tester' with a ready video before the module runs.

    This ensures the public user profile page has data to display when the
    Playwright tests access /u/tester.

    If database credentials are not available the fixture yields without
    setup so the test can still run (and skip gracefully).
    """
    config = DBConfig()

    # If no DB host/user configured, skip DB presetup — test will self-skip.
    if not os.getenv("DB_HOST") or not os.getenv("DB_USER"):
        yield
        return

    try:
        conn = psycopg2.connect(config.dsn())
        conn.autocommit = True
    except Exception as exc:
        print(f"[MYTUBE-115 presetup] DB connection failed: {exc} — skipping setup")
        yield
        return

    try:
        with conn.cursor() as cur:
            # Upsert the test user (idempotent across re-runs).
            cur.execute(
                """
                INSERT INTO users (firebase_uid, username)
                VALUES (%s, %s)
                ON CONFLICT (firebase_uid)
                    DO UPDATE SET username = EXCLUDED.username
                RETURNING id
                """,
                (_TEST_FIREBASE_UID, _TEST_USERNAME),
            )
            user_id = cur.fetchone()[0]

            # Remove any stale videos from a previous run so we start fresh.
            cur.execute(
                "DELETE FROM videos WHERE uploader_id = %s",
                (user_id,),
            )

            # Create a ready video with a valid thumbnail URL.
            video_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO videos
                    (id, uploader_id, title, status, thumbnail_url)
                VALUES (%s, %s, %s, 'ready', %s)
                """,
                (
                    video_id,
                    user_id,
                    "Test Video for MYTUBE-115",
                    _THUMB_TEMPLATE.format(vid=video_id),
                ),
            )

        print(
            f"[MYTUBE-115 presetup] Created ready video {video_id} for user '{_TEST_USERNAME}'"
        )
        yield

    finally:
        _cleanup_users(conn, [_TEST_USERNAME])
        print(f"[MYTUBE-115 teardown] Cleaned up user '{_TEST_USERNAME}'")
        conn.close()
