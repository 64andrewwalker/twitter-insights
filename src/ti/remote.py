"""HTTP client for remote mode queries."""

import requests


class RemoteError(Exception):
    """Error from remote ti server."""

    pass


class RemoteClient:
    """HTTP client that talks to ti-server's /v1/ API."""

    def __init__(
        self, api_url: str, api_key: str, timeout: int = 15, use_proxy: bool = True
    ):
        self.base_url = api_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._session = requests.Session()
        if not use_proxy:
            self._session.trust_env = False  # bypass system proxy

    def _headers(self) -> dict:
        return {"X-API-Key": self.api_key}

    def _get(self, path: str, params: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        resp = self._session.get(
            url, headers=self._headers(), params=params, timeout=self.timeout
        )
        resp.raise_for_status()
        return resp.json()

    def search(
        self, query: str, sort: str = "relevant", limit: int = 20, offset: int = 0
    ) -> dict:
        return self._get(
            "/v1/search", {"q": query, "sort": sort, "limit": limit, "offset": offset}
        )

    def tag(self, name: str, limit: int = 20, offset: int = 0) -> dict:
        return self._get(f"/v1/tag/{name}", {"limit": limit, "offset": offset})

    def tags(self) -> dict:
        return self._get("/v1/tags")

    def author(self, handle: str, limit: int = 20, offset: int = 0) -> dict:
        return self._get(f"/v1/author/{handle}", {"limit": limit, "offset": offset})

    def show(self, tweet_id: str) -> dict:
        return self._get(f"/v1/show/{tweet_id}")

    def latest(self, n: int = 20, offset: int = 0) -> dict:
        return self._get("/v1/latest", {"n": n, "offset": offset})

    def stats(self) -> dict:
        return self._get("/v1/stats")

    def db_versions(self, limit: int = 10) -> dict:
        return self._get("/v1/db/versions", {"limit": limit})

    def db_restore(self, version: str | None = None) -> dict:
        url = f"{self.base_url}/v1/db/restore"
        params = {"version": version} if version else {}
        resp = self._session.post(
            url, headers=self._headers(), params=params, timeout=60
        )
        resp.raise_for_status()
        return resp.json()
