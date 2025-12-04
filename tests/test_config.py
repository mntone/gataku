import pytest
import requests

from config import (
	RateLimitConfig,
	_parse_rate_per_minute,
	_parse_delay_value,
	load_config,
	GlobalConfig,
	InstanceConfig,
)
from classify import classify_origin_group, classify_account_group
from filters import should_skip
from fetch import run_instance
import types


def test_parse_rate_per_minute_string():
	assert _parse_rate_per_minute("2/minute") == pytest.approx(2.0)
	assert _parse_rate_per_minute("1/hour") == pytest.approx(1.0 / 60.0)


def test_parse_delay_value_from_rate():
	delay = _parse_delay_value("2/minute")
	assert delay == pytest.approx(30.0)


def test_rate_limit_override_controls_delay():
	cfg = RateLimitConfig(delay_seconds=6.0)
	cfg.set_override_rate("120/minute")
	assert cfg.delay_seconds == pytest.approx(0.5)


def test_load_config_download_rate_delay(tmp_path):
	cfg_file = tmp_path / "config.yaml"
	cfg_file.write_text(
		"""
download:
  filename_pattern: "{origin}/{index}"
  progress: off
  retry:
    max_attempts: 2
    delay: "5 seconds"
    rate_control: false
  rate:
    delay: "10 seconds"
""",
		encoding="utf-8",
	)

	cfg = load_config(cfg_file)
	assert cfg.download.rate.delay_seconds == pytest.approx(10.0)
	assert cfg.download.retry.delay_seconds == pytest.approx(5.0)


def test_load_config_download_rate_conflict(tmp_path):
	cfg_file = tmp_path / "config.yaml"
	cfg_file.write_text(
		"""
download:
  filename_pattern: "{origin}/{index}"
  progress: off
  retry:
    max_attempts: 2
    delay: "5 seconds"
    rate_control: false
  rate:
    default_rate: "2/minute"
    delay: "5 seconds"
""",
		encoding="utf-8",
	)

	with pytest.raises(ValueError):
		load_config(cfg_file)


def test_load_config_download_includes(tmp_path):
	cfg_file = tmp_path / "config.yaml"
	cfg_file.write_text(
		"""
download:
  filename_pattern: "{origin}/{index}"
  progress: off
  includes:
    gifv: true
    video: true
    audio: false
    thumbnail_only: true
    self: true
    nsfw: false
""",
		encoding="utf-8",
	)

	cfg = load_config(cfg_file)
	filter_cfg = cfg.download.filter
	assert filter_cfg.include_gifv is True
	assert filter_cfg.include_video is True
	assert filter_cfg.include_audio is False
	assert filter_cfg.include_thumbnail_only is True
	assert filter_cfg.include_self is True
	assert filter_cfg.include_nsfw is False


def test_default_classification_rules_apply():
	cfg = GlobalConfig()
	assert classify_origin_group("media.misskeyusercontent.com", cfg) == "misskey"
	assert classify_account_group("unknown.host", cfg) == "other"


def test_load_config_classify_rules_override(tmp_path):
	cfg_file = tmp_path / "config.yaml"
	cfg_file.write_text(
		"""
download:
  filename_pattern: "{origin}/{index}"
classify:
  rules:
    - match: "*.example.com"
      group: demo
    - match: "*"
      group: fallback
""",
		encoding="utf-8",
	)

	cfg = load_config(cfg_file)
	assert cfg.classify.rules[0].match == "*.example.com"
	assert classify_origin_group("cdn.EXAMPLE.com", cfg) == "demo"
	assert classify_account_group("other.host", cfg) == "fallback"


def test_load_config_download_user_agent(tmp_path):
	cfg_file = tmp_path / "config.yaml"
	cfg_file.write_text(
		"""
download:
  filename_pattern: "{origin}/{index}"
  progress: off
  useragent: "custom-agent/2.0"
""",
		encoding="utf-8",
	)

	cfg = load_config(cfg_file)
	assert cfg.download.user_agent == "custom-agent/2.0"


def test_load_config_removed_skip_window(tmp_path):
	cfg_file = tmp_path / "config.yaml"
	cfg_file.write_text(
		"""
removed:
  skip_media_not_found: "2 weeks"
""",
		encoding="utf-8",
	)

	cfg = load_config(cfg_file)
	assert cfg.removed.skip_media_not_found_for == pytest.approx(_parse_delay_value("2 weeks"))


def test_load_config_removed_skip_window_off(tmp_path):
	cfg_file = tmp_path / "config.yaml"
	cfg_file.write_text(
		"""
removed:
  skip_media_not_found: off
""",
		encoding="utf-8",
	)

	cfg = load_config(cfg_file)
	assert cfg.removed.skip_media_not_found_for is None


def test_filter_flags_control_skip():
	cfg = GlobalConfig()
	cfg.download.filter.include_nsfw = False
	cfg.download.filter.include_audio = False
	cfg.download.filter.include_video = False
	inst = InstanceConfig(
		name="test",
		base_url="https://example",
		access_token="token",
		account_id="123",
		account_handle="user@example",
	)

	status_nsfw = {
		"id": "1",
		"url": "https://example/status/1",
		"created_at": "2023-01-01T00:00:00Z",
		"account": {"id": "456", "username": "alice"},
		"media_attachments": [{"type": "image", "remote_url": "https://cdn/img.png"}],
		"sensitive": True,
	}
	assert should_skip(status_nsfw, inst, cfg) == (True, "nsfw_filtered")

	status_audio = {
		"id": "2",
		"url": "https://example/status/2",
		"created_at": "2023-01-01T00:00:00Z",
		"account": {"id": "456", "username": "alice"},
		"media_attachments": [{"type": "audio", "remote_url": "https://cdn/audio.mp3"}],
	}
	assert should_skip(status_audio, inst, cfg) == (True, "audio_media")

	cfg.download.filter.include_nsfw = True
	cfg.download.filter.include_audio = True
	assert should_skip(status_nsfw, inst, cfg) == (False, None)
	assert should_skip(status_audio, inst, cfg) == (False, None)


def test_try_unknown_media_respects_extensions():
	cfg = GlobalConfig()
	cfg.download.filter.include_video = False
	inst = InstanceConfig(
		name="test",
		base_url="https://example",
		access_token="token",
	)

	status_unknown = {
		"id": "3",
		"url": "https://example/status/3",
		"created_at": "2023-01-01T00:00:00Z",
		"account": {"id": "789", "username": "bob"},
		"media_attachments": [
			{"type": "unknown", "remote_url": "https://cdn/assets/picture.JPG"},
		],
	}

	assert should_skip(status_unknown, inst, cfg) == (True, "non_image_media")

	cfg.download.filter.try_unknown_media = True
	assert should_skip(status_unknown, inst, cfg) == (False, None)


def test_should_skip_self_posts_by_account_id():
	cfg = GlobalConfig()
	inst = InstanceConfig(
		name="self",
		base_url="https://example",
		access_token="token",
		account_id="42",
	)
	status = {
		"id": "4",
		"url": "https://example/status/4",
		"created_at": "2023-01-01T00:00:00Z",
		"account": {"id": "42", "username": "selfuser"},
		"media_attachments": [{"type": "image", "remote_url": "https://cdn/pic.png"}],
	}

	assert should_skip(status, inst, cfg) == (True, "self_post")


def test_should_skip_self_posts_by_handle_case_insensitive():
	cfg = GlobalConfig()
	inst = InstanceConfig(
		name="self",
		base_url="https://example",
		access_token="token",
		account_handle="User@Example.social",
	)
	status = {
		"id": "5",
		"url": "https://example/status/5",
		"created_at": "2023-01-01T00:00:00Z",
		"account": {
			"id": "55",
			"username": "user",
			"acct": "user@example.social",
		},
		"media_attachments": [{"type": "image", "remote_url": "https://cdn/item.png"}],
	}

	assert should_skip(status, inst, cfg) == (True, "self_post")


def test_include_self_flag_allows_self_posts():
	cfg = GlobalConfig()
	cfg.download.filter.include_self = True
	inst = InstanceConfig(
		name="self",
		base_url="https://example",
		access_token="token",
		account_id="42",
	)
	status = {
		"id": "6",
		"url": "https://example/status/6",
		"created_at": "2023-01-01T00:00:00Z",
		"account": {"id": "42", "username": "selfuser"},
		"media_attachments": [{"type": "image", "remote_url": "https://cdn/pic.png"}],
	}

	assert should_skip(status, inst, cfg) == (False, None)


def test_thumbnail_only_filter_requires_remote_urls():
	cfg = GlobalConfig()
	cfg.download.filter.include_thumbnail_only = False
	inst = InstanceConfig(
		name="thumb",
		base_url="https://example",
		access_token="token",
	)
	status = {
		"id": "7",
		"url": "https://example/status/7",
		"created_at": "2023-01-01T00:00:00Z",
		"account": {"id": "70", "username": "thumbuser"},
		"media_attachments": [{"type": "image", "remote_url": None}],
	}

	assert should_skip(status, inst, cfg) == (True, "no_remote_url")


def test_include_thumbnail_only_allows_missing_remote_urls_when_try_unknown_enabled():
	cfg = GlobalConfig()
	cfg.download.filter.include_thumbnail_only = True
	cfg.download.filter.try_unknown_media = True
	inst = InstanceConfig(
		name="thumb",
		base_url="https://example",
		access_token="token",
	)
	status = {
		"id": "8",
		"url": "https://example/status/8",
		"created_at": "2023-01-01T00:00:00Z",
		"account": {"id": "80", "username": "thumbuser"},
		"media_attachments": [
			{"type": "unknown", "remote_url": None, "url": "https://cdn/pic.JPEG"},
		],
	}

	assert should_skip(status, inst, cfg) == (False, None)


def test_missing_media_404_logged(monkeypatch, tmp_path):
	cfg = GlobalConfig()
	cfg.runtime.limit = 1
	cfg.runtime.dry_run = False
	cfg.logging.log_removed = True
	cfg.download.progress_level = "off"
	cfg.paths.download = tmp_path / "download"
	cfg.paths.logs = tmp_path / "logs"
	cfg.paths.tmp = tmp_path / "tmp"
	cfg.paths.archive = tmp_path / "archive"
	for p in [cfg.paths.download, cfg.paths.logs, cfg.paths.tmp, cfg.paths.archive]:
		p.mkdir(parents=True, exist_ok=True)

	inst = InstanceConfig(
		name="mastodon",
		base_url="https://example",
		access_token="token",
	)

	statuses = [
		{
			"id": "10",
			"url": "https://example/10",
			"created_at": "2023-01-01T00:00:00Z",
			"media_attachments": [
				{"remote_url": "https://cdn/missing.png"},
			],
		}
	]

	class DummyAPI:
		def __init__(self, data):
			self.data = data

		def fetch_bookmarks(self):
			for s in self.data:
				yield s

	removed = []
	dummy_db = types.SimpleNamespace(
		get=lambda sha: None,
		set=lambda record: None,
		log_removed=lambda entry: removed.append(entry),
	)

	response = requests.Response()
	response.status_code = 404
	error = requests.HTTPError(response=response)

	def fake_download(url, config, progress_label=None):
		raise error

	monkeypatch.setattr("fetch.download_and_sha256", fake_download)
	monkeypatch.setattr("fetch.time.sleep", lambda delay: None)

	api = DummyAPI(statuses)

	run_instance(inst, api, dummy_db, cfg)

	assert removed
	assert removed[0]["reason"] == "media_not_found"


def test_progress_label_formatting(monkeypatch, tmp_path):
	cfg = GlobalConfig()
	cfg.download.progress_level = "filesize"
	cfg.download.rate.delay_seconds = 0
	cfg.runtime.limit = 3
	cfg.runtime.dry_run = True
	cfg.paths.download = tmp_path / "download"
	cfg.paths.logs = tmp_path / "logs"
	cfg.paths.tmp = tmp_path / "tmp"
	cfg.paths.archive = tmp_path / "archive"
	for p in [cfg.paths.download, cfg.paths.logs, cfg.paths.tmp, cfg.paths.archive]:
		p.mkdir(parents=True, exist_ok=True)

	inst = InstanceConfig(
		name="mastodon",
		base_url="https://example",
		access_token="token",
	)

	statuses = [
		{
			"id": "1",
			"url": "https://example/1",
			"created_at": "2023-01-01T00:00:00Z",
			"media_attachments": [
				{"remote_url": "https://cdn/img1.png"},
				{"remote_url": "https://cdn/img2.png"},
			],
		},
		{
			"id": "2",
			"url": "https://example/2",
			"created_at": "2023-01-01T00:00:00Z",
			"media_attachments": [
				{"remote_url": "https://cdn/img3.png"},
			],
		},
	]

	class DummyAPI:
		def __init__(self, data):
			self.data = data

		def fetch_bookmarks(self):
			for s in self.data:
				yield s

	dummy_db = types.SimpleNamespace(
		get=lambda sha: None,
		set=lambda record: None,
		log_removed=lambda entry: None,
	)

	progress_labels = []

	def fake_download(url, config, progress_label=None):
		progress_labels.append(progress_label)
		tmp_file = tmp_path / f"tmp-{len(progress_labels)}.bin"
		tmp_file.write_text("data")
		return str(tmp_file), "sha", 10

	monkeypatch.setattr("fetch.download_and_sha256", fake_download)
	monkeypatch.setattr("fetch.time.sleep", lambda delay: None)

	api = DummyAPI(statuses)

	run_instance(inst, api, dummy_db, cfg)

	assert progress_labels[0] == "[mastodon] 1/3 media 1/2"
	assert progress_labels[1] == "[mastodon] 1/3 media 2/2"
	assert progress_labels[2] == "[mastodon] 2/3 media"
