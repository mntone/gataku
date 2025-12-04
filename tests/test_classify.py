import pytest

from classify import (
	classify_origin_host,
	classify_origin_group,
	classify_account_host,
	classify_account_group,
)


@pytest.mark.parametrize(
	"url,expected",
	[
		("https://example.social/@user/1", "example.social"),
		("https://cdn.example/media/file.png", "cdn.example"),
		("not a url", ""),
	],
)
def test_classify_origin_host_parses_hostname(url, expected):
	assert classify_origin_host(url) == expected


@pytest.mark.parametrize(
	"host,expected",
	[
		("Misskey.io", "misskey"),
		("mastodon.social", "mastodon"),
		("foo.mstdn.jp", "mastodon"),
		("pawoo.net", "pawoo"),
		("unknown.example", "other"),
	],
)
def test_classify_origin_group_variants(host, expected):
	assert classify_origin_group(host) == expected


def test_classify_account_host_falls_back_to_unknown_when_no_url():
	status = {"url": None}
	assert classify_account_host(status) == "unknown"


def test_classify_account_group_same_logic_as_origin_group():
	assert classify_account_group("misskey.space") == "misskey"
	assert classify_account_group("something") == "other"
