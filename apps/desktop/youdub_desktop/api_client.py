from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx


class ApiClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/api/health")

    def list_tasks(self, limit: int = 100) -> list[dict[str, Any]]:
        return self._request("GET", f"/api/tasks?limit={limit}")["tasks"]

    def get_task(self, task_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/tasks/{task_id}")

    def get_log(self, task_id: str) -> str:
        with httpx.Client(timeout=15) as client:
            response = client.get(f"{self.base_url}/api/tasks/{task_id}/log")
            self._raise_for_status(response)
            return response.text

    def create_task(self, url: str) -> dict[str, Any]:
        return self._request("POST", "/api/tasks", json={"url": url})

    def upload_task(self, file_path: Path, direction: str) -> dict[str, Any]:
        with httpx.Client(timeout=None) as client:
            with file_path.open("rb") as handle:
                response = client.post(
                    f"{self.base_url}/api/tasks/upload",
                    data={"direction": direction},
                    files={"file": (file_path.name, handle, "application/octet-stream")},
                )
            self._raise_for_status(response)
            return response.json()

    def delete_task(self, task_id: str) -> None:
        self._request("DELETE", f"/api/tasks/{task_id}")

    def rerun_task(self, task_id: str) -> dict[str, Any]:
        return self._request("POST", f"/api/tasks/{task_id}/rerun")

    def resume_task(self, task_id: str) -> dict[str, Any]:
        return self._request("POST", f"/api/tasks/{task_id}/resume")

    def get_cookie_info(self) -> dict[str, Any]:
        return self._request("GET", "/api/cookies/youtube")

    def save_cookie(self, content: str) -> dict[str, Any]:
        return self._request("POST", "/api/cookies/youtube", json={"content": content})

    def get_openai_settings(self) -> dict[str, Any]:
        return self._request("GET", "/api/settings/openai")

    def save_openai_settings(self, settings: dict[str, str]) -> dict[str, Any]:
        return self._request("POST", "/api/settings/openai", json=settings)

    def list_models(self, base_url: str, api_key: str) -> list[str]:
        payload = self._request(
            "POST",
            "/api/settings/openai/models",
            json={"base_url": base_url, "api_key": api_key},
        )
        return payload["models"]

    def get_ytdlp_settings(self) -> dict[str, Any]:
        return self._request("GET", "/api/settings/ytdlp")

    def save_ytdlp_settings(self, proxy_port: str) -> dict[str, Any]:
        return self._request("POST", "/api/settings/ytdlp", json={"proxy_port": proxy_port})

    def final_video_url(self, task_id: str) -> str:
        return f"{self.base_url}/api/tasks/{task_id}/artifact/final-video"

    def _request(self, method: str, path: str, **kwargs) -> Any:
        with httpx.Client(timeout=30) as client:
            response = client.request(method, f"{self.base_url}{path}", **kwargs)
            self._raise_for_status(response)
            if response.status_code == 204:
                return None
            return response.json()

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.is_success:
            return
        try:
            detail = response.json().get("detail")
        except Exception:  # noqa: BLE001
            detail = response.text
        raise RuntimeError(detail or f"Request failed: {response.status_code}")
