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

    def put(self, path: str, payload: dict, extra_headers: Optional[dict] = None) -> tuple[int, str]:
        """Issue an authenticated PUT *path* with a JSON body.

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
        req = urllib.request.Request(url, data=data, method="PUT", headers=headers)
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

    def post_multipart(
        self,
        path: str,
        fields: dict,
        files: dict,
        extra_headers: Optional[dict] = None,
    ) -> tuple[int, str]:
        """Issue an authenticated POST *path* with a multipart/form-data body.

        *fields* is a dict of plain text fields {name: value}.
        *files* is a dict of file fields {name: (filename, data_bytes, content_type)}.

        Returns (status_code, response_body).
        """
        import email.generator
        import io
        import mimetypes
        import uuid

        boundary = uuid.uuid4().hex
        body_parts: list[bytes] = []
        for name, value in fields.items():
            body_parts.append(
                f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
            )
        for name, (filename, data_bytes, content_type) in files.items():
            header = (
                f'--{boundary}\r\n'
                f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                f'Content-Type: {content_type}\r\n\r\n'
            ).encode()
            body_parts.append(header + data_bytes + b"\r\n")
        body_parts.append(f'--{boundary}--\r\n'.encode())
        body = b"".join(body_parts)

        url = f"{self._base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        }
        if extra_headers:
            headers.update(extra_headers)
        req = urllib.request.Request(url, data=body, method="POST", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.status, resp.read().decode()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode()

    @staticmethod
    def sign_in_with_email_password(api_key: str, email: str, password: str) -> Optional[str]:
        """Sign in with Firebase email/password; return the ID token or None on error."""
        import json
        url = (
            "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
            "?key=" + api_key
        )
        try:
            data = json.dumps(
                {"email": email, "password": password, "returnSecureToken": True}
            ).encode()
            req = urllib.request.Request(
                url, data=data, headers={"Content-Type": "application/json"}, method="POST"
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode()).get("idToken")
        except Exception:
            return None
