import hashlib
from pathlib import Path

import pytest
import requests

from config import GlobalConfig
from downloader import _format_bytes, _attempt_download, download_and_sha256


@pytest.mark.parametrize(
	"size,expected",
	[
		(512, "512 B"),
		(1024, "1.00 KB"),
		(10 * 1024, "10.0 KB"),
		(1024 ** 2, "1.00 MB"),
		(5 * 1024 ** 2, "5.00 MB"),
		(1024 ** 3, "1.00 GB"),
	],
)
def test_format_bytes_converts_units(size, expected):
	assert _format_bytes(size) == expected


def test_format_bytes_shows_two_decimals_under_ten():
	assert _format_bytes(5 * 1024 ** 2 + 100) == "5.00 MB"


def test_attempt_download_writes_file_and_hash(monkeypatch):
	cfg = GlobalConfig()
	cfg.download.progress_level = "off"

	chunks = [b"hello ", b"world"]
	class DummyResponse:
		def __init__(self):
			self.headers = {"content-length": str(sum(len(c) for c in chunks))}

		def raise_for_status(self):
			pass

		def iter_content(self, chunk_size):
			for chunk in chunks:
				yield chunk

	def fake_get(url, stream=True, timeout=15, headers=None):
		return DummyResponse()

	monkeypatch.setattr("downloader.requests.get", fake_get)

	tmp_path, sha256, size = _attempt_download("https://example/file", cfg, progress_label=None)

	assert size == sum(len(c) for c in chunks)
	expected_hash = hashlib.sha256(b"".join(chunks)).hexdigest()
	assert sha256 == expected_hash
	assert Path(tmp_path).read_bytes() == b"".join(chunks)
	Path(tmp_path).unlink()


def test_attempt_download_propagates_http_error(monkeypatch):
	cfg = GlobalConfig()

	class ErrResponse:
		def raise_for_status(self):
			raise requests.HTTPError("boom")

	def fake_get(url, stream=True, timeout=15, headers=None):
		return ErrResponse()

	monkeypatch.setattr("downloader.requests.get", fake_get)

	with pytest.raises(requests.HTTPError):
		_attempt_download("https://example/file", cfg, progress_label=None)


def test_download_and_sha256_retries_then_succeeds(monkeypatch):
	cfg = GlobalConfig()
	cfg.download.retry.max_attempts = 3
	cfg.download.retry.rate_control = False
	cfg.download.retry.delay_seconds = 0

	call_count = {"value": 0}

	def fake_attempt(url, config, label):
		call_count["value"] += 1
		if call_count["value"] < 2:
			raise requests.ConnectionError("fail once")
		return "/tmp/file", "deadbeef", 10

	monkeypatch.setattr("downloader._attempt_download", fake_attempt)
	monkeypatch.setattr("downloader.time.sleep", lambda delay: (_ := delay))

	path, sha, size = download_and_sha256("https://example/file", cfg)

	assert (path, sha, size) == ("/tmp/file", "deadbeef", 10)
	assert call_count["value"] == 2


def test_download_and_sha256_raises_after_exhausting(monkeypatch):
	cfg = GlobalConfig()
	cfg.download.retry.max_attempts = 2
	cfg.download.retry.rate_control = True
	cfg.download.rate.delay_seconds = 0

	monkeypatch.setattr(
		"downloader._attempt_download",
		lambda url, config, label: (_ for _ in ()).throw(requests.HTTPError("boom")),
	)
	monkeypatch.setattr("downloader.time.sleep", lambda delay: (_ := delay))

	with pytest.raises(requests.HTTPError):
		download_and_sha256("https://example/file", cfg)
