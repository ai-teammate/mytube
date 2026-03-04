"""
Presetup for MYTUBE-146 test suite.

Creates a stable test user (testuser_mytube146) and a ready video with
hls_manifest_path set before the Playwright tests run. The generated video
UUID is injected into MYTUBE_146_VIDEO_ID so the existing ready_video
fixture picks it up without any modification.

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

_TEST_USERNAME    = "testuser_mytube146"
_TEST_FIREBASE_UID = "firebase_uid_mytube146"
_HLS_TEMPLATE      = "gs://mytube-hls-output/videos/{vid}/index.m3u8"
_THUMB_TEMPLATE    = "https://storage.googleapis.com/mytube-hls-output/videos/{vid}/thumbnail.jpg"


@pytest.fixture(scope="module", autouse=True)
def setup_test_video() -> None:
    """Insert a ready video owned by testuser_mytube146 before the module runs.

    The video UUID is written to MYTUBE_146_VIDEO_ID so VideoApiService
    uses it directly via the override_id path (no discovery needed).

    If database credentials are not available the fixture yields without
    setup so the test can still run (and skip gracefully via pytest.skip
    inside the ready_video fixture).
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
        print(f"[MYTUBE-146 presetup] DB connection failed: {exc} — skipping setup")
        yield
        return

    video_id: str | None = None
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

            # Remove any stale video from a previous run so the UUID is fresh.
            cur.execute(
                "DELETE FROM videos WHERE uploader_id = %s",
                (user_id,),
            )

            # Create a ready video with a valid HLS manifest path.
            video_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO videos
                    (id, uploader_id, title, status, hls_manifest_path, thumbnail_url)
                VALUES (%s, %s, %s, 'ready', %s, %s)
                """,
                (
                    video_id,
                    user_id,
                    "MYTUBE-146 Test Video",
                    _HLS_TEMPLATE.format(vid=video_id),
                    _THUMB_TEMPLATE.format(vid=video_id),
                ),
            )

        os.environ["MYTUBE_146_VIDEO_ID"] = video_id
        print(f"[MYTUBE-146 presetup] Created ready video {video_id} for {_TEST_USERNAME}")
        yield

    finally:
        os.environ.pop("MYTUBE_146_VIDEO_ID", None)
        _cleanup_users(conn, [_TEST_USERNAME])
        print(f"[MYTUBE-146 teardown] Cleaned up {_TEST_USERNAME}")
        conn.close()
