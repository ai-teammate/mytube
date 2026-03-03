"""Service object for making authenticated HTTP requests using a Bearer token."""
import os
import urllib.request
import urllib.error
from typing import Optional


class AuthService:
    """Provides helpers for issuing HTTP requests with a Firebase Bearer token.

    The token is injected via constructor to allow tests to supply tokens from
    environment variables without hardcoding any values inside this class.

    Usage::

        svc = AuthService(base_url="http://localhost:8080", token=os.getenv("FIREBASE_TEST_TOKEN"))
        status, body = svc.get("/api/me")
    """

    def __init__(self, base_url: str, token: str):
        self._base_url = base_url.rstrip("/")
        self._token = token

    def get(self, path: str, extra_headers: Optional[dict] = None) -> tuple[int, str]:
        """Issue GET *path* with Authorization: Bearer header.

        Returns (status_code, response_body).
        """
        url = f"{self._base_url}{path}"
        headers = {"Authorization": f"Bearer {self._token}"}
        if extra_headers:
            headers.update(extra_headers)
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, resp.read().decode()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode()

    def post(self, path: str, payload: dict, extra_headers: Optional[dict] = None) -> tuple[int, str]:
        """Issue an authenticated POST *path* with a JSON body.

        Serialises *payload* as JSON, sets Content-Type to application/json,
        and includes Authorization: Bearer header.

        Returns (status_code, response_body).
        """
        import json
        url = f"{self._base_url}{path}"
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
        if extra_headers:
            headers.update(extra_headers)
        req = urllib.request.Request(url, data=data, method="POST", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, resp.read().decode()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode()

    def delete(self, path: str, extra_headers: Optional[dict] = None) -> tuple[int, str]:
        """Issue an authenticated DELETE *path*.

        Includes Authorization: Bearer header.

        Returns (status_code, response_body).
        """
        url = f"{self._base_url}{path}"
        headers = {"Authorization": f"Bearer {self._token}"}
        if extra_headers:
            headers.update(extra_headers)
        req = urllib.request.Request(url, method="DELETE", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, resp.read().decode()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode()
