from urllib.parse import urlparse

__all__ = [
    "ALLOWED_URL_SCHEMES",
    "CLOUDFLARE_CHALLENGE_MARKERS",
    "CloudflareChallengeNotSolved",
    "ensure_safe_url",
    "verify_cloudflare_solved",
]

ALLOWED_URL_SCHEMES: frozenset[str] = frozenset({"http", "https"})

CLOUDFLARE_CHALLENGE_MARKERS: tuple[str, ...] = (
    "challenges.cloudflare.com",
    "cf-turnstile",
    "cf_turnstile",
    "just a moment",
    "cf_chl_",
    "verifying you are human",
    "ctype: 'non-interactive'",
    "ctype: 'managed'",
    "ctype: 'interactive'",
)


class CloudflareChallengeNotSolved(RuntimeError):
    """Raised when a Cloudflare challenge remains unsolved after solver execution."""


def ensure_safe_url(url: str) -> str:
    """Ensure *url* uses an allowed scheme (http/https, case-insensitive) and has a netloc."""
    if not isinstance(url, str) or not url.strip():
        raise ValueError("URL must be a non-empty string.")
    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    if scheme not in ALLOWED_URL_SCHEMES or not parsed.netloc or not parsed.hostname:
        raise ValueError(f"Unsafe or unsupported URL {url!r}: only http/https URLs with a valid host are allowed.")
    return url


def verify_cloudflare_solved(html: str | bytes, status: int) -> bool:
    """Verify that post-solve HTML has no Cloudflare challenge markers and HTTP status < 400."""
    if status is None or not isinstance(status, int) or status >= 400 or status < 100:
        raise CloudflareChallengeNotSolved(f"Cloudflare challenge not solved (HTTP status {status}).")

    if isinstance(html, bytes):
        content = html.decode("utf-8", errors="ignore")
    elif isinstance(html, str):
        content = html
    else:
        raise CloudflareChallengeNotSolved("Invalid HTML content type.")

    lowered = content.lower()
    for marker in CLOUDFLARE_CHALLENGE_MARKERS:
        if marker in lowered:
            raise CloudflareChallengeNotSolved(
                f"Cloudflare challenge not solved: marker {marker!r} still present in page content."
            )
    return True
