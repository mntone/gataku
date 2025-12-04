from fnmatch import fnmatch
from typing import Any, Dict, Iterable
from urllib.parse import urlparse


DEFAULT_CLASSIFICATION_RULE_SPECS = (
	{"match": "*misskey*", "group": "misskey"},
	{"match": "*mastodon*", "group": "mastodon"},
	{"match": "*.mstdn.jp", "group": "mastodon"},
	{"match": "pawoo.net", "group": "pawoo"},
	{"match": "*", "group": "other"},
)


def classify_origin_host(url: str) -> str:
	"""Return the hostname for a media URL (or empty string when missing)."""
	return urlparse(url).hostname or ""


def classify_origin_group(host: str, config: Any | None = None) -> str:
	"""Group origin hosts using user-configured classification rules."""
	return _classify_host(host, config)


def classify_account_host(status: Dict[str, Any]) -> str:
	"""Derive the account host from a status (parsing URL when needed)."""
	url = status.get("url")
	if not url:
		return "unknown"
	return urlparse(url).hostname or "unknown"


def classify_account_group(host: str, config: Any | None = None) -> str:
	"""Group account hosts using the same rules as origin hosts."""
	return _classify_host(host, config)


def _classify_host(host: str | None, config: Any | None) -> str:
	if not host:
		return "other"

	host_lower = host.lower()
	for match, group in _iter_rules(config):
		if match and fnmatch(host_lower, match):
			return group

	return "other"


def _iter_rules(config: Any | None) -> Iterable[tuple[str, str]]:
	if config is not None:
		classify_cfg = getattr(config, "classify", config)
		rules = getattr(classify_cfg, "rules", None)
		if rules:
			for rule in rules:
				match = getattr(rule, "match", None)
				group = getattr(rule, "group", None)
				if (match is None or group is None) and isinstance(rule, dict):
					if match is None:
						match = rule.get("match")
					if group is None:
						group = rule.get("group")
				if match and group:
					yield str(match).lower(), str(group)
			return

	for spec in DEFAULT_CLASSIFICATION_RULE_SPECS:
		yield spec["match"].lower(), spec["group"]
