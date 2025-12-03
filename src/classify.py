from typing import Any, Dict
from urllib.parse import urlparse


def classify_origin_host(url: str) -> str:
	"""Return the hostname for a media URL (or empty string when missing)."""
	host = urlparse(url).hostname or ""
	return host


def classify_origin_group(host: str) -> str:
	"""Group origin hosts into coarse categories for reporting."""
	h = host.lower()
	if "misskey" in h:
		return "misskey"
	if "pawoo" in h:
		return "pawoo"
	if "mastodon" in h:
		return "mastodon"
	if h.endswith("mstdn.jp"):
		return "mastodon"
	return "other"


def classify_account_host(status: Dict[str, Any]) -> str:
	"""Derive the account host from a status (parsing URL when needed)."""
	url = status.get("url")
	if not url:
		return "unknown"
	return urlparse(url).hostname or "unknown"


def classify_account_group(host: str) -> str:
	"""Group account hosts into the same categories as origin hosts."""
	h = host.lower()
	if "misskey" in h:
		return "misskey"
	if "pawoo" in h:
		return "pawoo"
	if "mastodon" in h:
		return "mastodon"
	if h.endswith("mstdn.jp"):
		return "mastodon"
	return "other"
