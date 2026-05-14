import httpx

from cli import config


def get_base_url() -> str:
    return config.get("api_url", "http://localhost:8000").rstrip("/")


def get_api_key() -> str | None:
    return config.get("api_key")


def get_headers() -> dict[str, str]:
    headers: dict[str, str] = {"Content-Type": "application/json"}
    api_key = get_api_key()
    if api_key:
        headers["X-Api-Key"] = api_key
    return headers


def api_url(path: str) -> str:
    return f"{get_base_url()}/api/v1{path}"


def get_client(**kwargs) -> httpx.Client:
    return httpx.Client(headers=get_headers(), timeout=30, **kwargs)
