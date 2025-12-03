from datetime import datetime


def parse_time(value: str) -> datetime:
	"""
	Parse an ISO8601 timestamp into a timezone-aware datetime.
	Supports trailing 'Z' (UTC) and offset-aware strings.
	"""
	if not value:
		raise ValueError("timestamp is empty")
	value = value.replace("Z", "+00:00")
	return datetime.fromisoformat(value)
