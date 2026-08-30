import logging
from typing import Any, List
import httpx

logger = logging.getLogger(__name__)


class GitHubConnectionError(RuntimeError):
    """A safe, user-facing GitHub connection or synchronization error."""


def _github_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


async def fetch_github_repositories(
    token_data: dict[str, Any] | None,
    max_results: int = 10,
) -> List[dict[str, Any]]:
    """Fetch repositories visible to the authenticated GitHub user."""
    if not token_data or not token_data.get("access_token"):
        raise GitHubConnectionError("GitHub authorization is missing. Reconnect GitHub and try again.")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                "https://api.github.com/user/repos",
                headers=_github_headers(token_data["access_token"]),
                params={
                    "affiliation": "owner,collaborator,organization_member",
                    "sort": "updated",
                    "direction": "desc",
                    "per_page": max(1, min(max_results, 30)),
                },
            )
            response.raise_for_status()
            return [
                {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "full_name": item.get("full_name"),
                    "description": item.get("description") or "",
                    "private": bool(item.get("private")),
                    "fork": bool(item.get("fork")),
                    "language": item.get("language"),
                    "stars": item.get("stargazers_count", 0),
                    "open_issues": item.get("open_issues_count", 0),
                    "updated_at": item.get("updated_at"),
                    "html_url": item.get("html_url"),
                }
                for item in response.json()
            ]
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        logger.warning("GitHub repository request failed with status %s", status)
        if status in (401, 403):
            raise GitHubConnectionError("GitHub authorization expired or was denied. Reconnect GitHub to continue.") from exc
        raise GitHubConnectionError("GitHub repositories could not be loaded. Try again shortly.") from exc
    except httpx.HTTPError as exc:
        logger.warning("Failed to fetch GitHub repositories: %s", exc)
        raise GitHubConnectionError("GitHub could not be reached. Try again shortly.") from exc


async def fetch_github_prs(
    token_data: dict[str, Any] | None,
) -> List[dict[str, Any]]:
    """Fetches open pull requests involving or assigned to the user."""
    if not token_data or not token_data.get("access_token"):
        return []

    token = token_data.get("access_token")
    headers = _github_headers(token)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.github.com/user/issues?filter=all&state=open&pulls=true",
                headers=headers,
            )
            if resp.status_code == 200:
                items = resp.json()
                prs = []
                for item in items[:15]:
                    if "pull_request" in item:
                        prs.append({
                            "id": item.get("id"),
                            "number": item.get("number"),
                            "title": item.get("title"),
                            "repository": item.get("repository", {}).get("full_name"),
                            "html_url": item.get("html_url"),
                            "state": item.get("state"),
                            "created_at": item.get("created_at"),
                            "user": item.get("user", {}).get("login"),
                        })
                return prs
    except Exception as e:
        logger.warning("Failed to fetch GitHub PRs: %s", e)
    return []


async def fetch_github_issues(
    token_data: dict[str, Any] | None,
) -> List[dict[str, Any]]:
    """Fetches open issues assigned to the user."""
    if not token_data or not token_data.get("access_token"):
        return []

    token = token_data.get("access_token")
    headers = _github_headers(token)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.github.com/issues?filter=assigned&state=open",
                headers=headers,
            )
            if resp.status_code == 200:
                items = resp.json()
                issues = []
                for item in items[:15]:
                    if "pull_request" not in item:
                        issues.append({
                            "id": item.get("id"),
                            "number": item.get("number"),
                            "title": item.get("title"),
                            "repository": item.get("repository", {}).get("full_name"),
                            "html_url": item.get("html_url"),
                            "state": item.get("state"),
                            "created_at": item.get("created_at"),
                        })
                return issues
    except Exception as e:
        logger.warning("Failed to fetch GitHub issues: %s", e)
    return []
