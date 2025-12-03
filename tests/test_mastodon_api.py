from config import InstanceConfig
from mastodon_api import MastodonAPI


def test_parse_next_max_id_extracts_query_param():
	links = {
		"next": {
			"url": "https://example/api/v1/bookmarks?max_id=12345&since_id=1",
		}
	}

	assert MastodonAPI._parse_next_max_id(links) == "12345"


def test_parse_next_max_id_returns_none_when_missing():
	assert MastodonAPI._parse_next_max_id({"prev": {"url": "https://example"}}) is None
	assert MastodonAPI._parse_next_max_id({"next": {"url": "https://example"}}) is None


def test_fetch_bookmarks_iterates_pages(monkeypatch):
	inst = InstanceConfig(
		name="test",
		base_url="https://example",
		access_token="token",
	)
	api = MastodonAPI(inst)

	pages = [
		([{"id": "1"}], "m1"),
		([{"id": "2"}], None),
	]

	calls = []

	def fake_fetch(self, max_id=None, limit=40):
		calls.append(max_id)
		data, next_id = pages.pop(0)
		return data, next_id

	monkeypatch.setattr(MastodonAPI, "_fetch_bookmarks_page", fake_fetch, raising=False)

	results = list(api.fetch_bookmarks())

	assert [status["id"] for status in results] == ["1", "2"]
	assert calls == [None, "m1"]


def test_fetch_bookmarks_page_parses_links(monkeypatch):
	inst = InstanceConfig(
		name="test",
		base_url="https://example",
		access_token="token",
	)
	api = MastodonAPI(inst)

	captured = {}

	class DummyResponse:
		def __init__(self):
			self.status_code = 200
			self.links = {
				"next": {
					"url": "https://example/api/v1/bookmarks?max_id=next123",
				}
			}

		def raise_for_status(self):
			pass

		def json(self):
			return [{"id": "a"}]

	def fake_get(url, headers, params, timeout):
		captured["url"] = url
		captured["headers"] = headers
		captured["params"] = params
		return DummyResponse()

	monkeypatch.setattr("mastodon_api.requests.get", fake_get)

	data, next_id = api._fetch_bookmarks_page(max_id="prev", limit=2)

	assert data == [{"id": "a"}]
	assert next_id == "next123"
	assert captured["params"]["max_id"] == "prev"
	assert captured["params"]["limit"] == 2
	assert "Authorization" in captured["headers"]
