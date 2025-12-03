from datetime import datetime, timezone, timedelta

import pytest

from util import parse_time


def test_parse_time_handles_z_suffix():
	result = parse_time("2023-01-01T12:34:56Z")
	assert result == datetime(2023, 1, 1, 12, 34, 56, tzinfo=timezone.utc)


def test_parse_time_preserves_timezone_offset():
	result = parse_time("2023-01-01T09:00:00+09:00")
	assert result.hour == 9
	assert result.utcoffset() == timedelta(hours=9)


def test_parse_time_rejects_empty_string():
	with pytest.raises(ValueError):
		parse_time("")
