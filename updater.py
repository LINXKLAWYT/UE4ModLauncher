"""
Update check: asks GitHub for the latest published release and reports
whether it is newer than the running version. Uses only the standard
library and never raises - offline, rate-limited, or no releases yet all
just mean "no update to show".
"""
import json
import re
import urllib.request

from config import APP_VERSION, LATEST_RELEASE_API, RELEASES_URL

def _version_string(text):
    """
    Pulls the version number out of a release tag, ignoring digits that are
    part of a name. 'v1.2.3' -> '1.2.3', 'UE4ModLauncher1.1' -> '1.1'
    ("UE4" must not count). Falls back to 'v2' -> '2'. None if not found.
    """
    text = text or ""
    m = re.search(r"\d+(?:\.\d+)+", text)
    if m:
        return m.group(0)
    m = re.search(r"(?<![A-Za-z0-9])[vV](\d+)", text)
    return m.group(1) if m else None


def _parse_version(text):
    v = _version_string(text)
    if v is None:
        return None
    parts = [int(n) for n in v.split(".")[:4]]
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def is_newer(latest, current):
    a, b = _parse_version(latest), _parse_version(current)
    return a is not None and b is not None and a > b


def check_for_update(timeout=5):
    """
    Returns {"latest": "<tag>", "url": <releases page>} if a newer release
    exists, otherwise None.
    """
    try:
        req = urllib.request.Request(
            LATEST_RELEASE_API,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "UE4ModLauncher-update-check",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        tag = data.get("tag_name") or data.get("name") or ""
        if is_newer(tag, APP_VERSION):
            return {"latest": _version_string(tag) or tag, "url": RELEASES_URL}
    except Exception:
        pass
    return None
