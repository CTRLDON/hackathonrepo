"""Source hygiene: a bare homepage (https://www.statista.com/) backs no specific claim."""
from __future__ import annotations
import re
from urllib.parse import urlparse

_LOCALE = re.compile(r"[a-z]{2}([-_][a-z]{2})?", re.I)  # /en, /en-us: a localised homepage


def specific(urls) -> list[str]:
    """Keep http(s) URLs that point at a specific page, de-duplicated, in order."""
    out = []
    for u in urls or []:
        p = urlparse(str(u))
        path = p.path.strip("/")
        homepage = not path or bool(_LOCALE.fullmatch(path)) or path.lower() in ("index.html", "home", "en/home")
        if p.scheme in ("http", "https") and p.netloc and not homepage and u not in out:
            out.append(u)
    return out
