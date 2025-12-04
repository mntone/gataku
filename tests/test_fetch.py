import datetime
import json
from pathlib import Path

import requests

from config import GlobalConfig, InstanceConfig
from filenames import build_log_path
from fetch import (
	RemovedMediaTracker,
	_safe_parse_created,
	_guess_extension,
	log_download,
	log_removed,
	process_status,
)
from helpers import make_status


class DummyDB:
	def __init__(self, entry=None):
		self.entry = entry
		self.set_calls = []
		self.logged = []

	def get(self, sha):
		if self.entry and sha == self.entry["sha256"]:
			return self.entry
		return None

	def set(self, record):
		self.set_calls.append(record)

	def log_removed(self, record):
		self.logged.append(record)


class DummyTracker:
	def __init__(self, skipped=None):
		self.skipped = set(skipped or [])
		self.recorded = []

	def should_skip(self, url):
		return url in self.skipped

	def record(self, urls):
		self.recorded.extend(urls)


def _make_config(tmp_path: Path, dry_run: bool = False) -> GlobalConfig:
	cfg = GlobalConfig()
	cfg.runtime.dry_run = dry_run
	cfg.paths.download = tmp_path / "download"
	cfg.paths.logs = tmp_path / "logs"
	cfg.paths.tmp = tmp_path / "tmp"
	cfg.paths.archive = tmp_path / "archive"
	for p in [cfg.paths.download, cfg.paths.logs, cfg.paths.tmp, cfg.paths.archive]:
		p.mkdir(parents=True, exist_ok=True)
	return cfg


def _run_process_status(
	status,
	inst,
	db,
	cfg,
	monkeypatch,
	tmp_path,
	sha="abc123",
	download_func=None,
	return_tmp=False,
	removed_tracker=None,
):
	tmpfile = tmp_path / "temp.bin"

	def default_download(url, config, progress_label=None):
		tmpfile.write_bytes(b"x")
		return str(tmpfile), sha, 1

	def wrapper(url, config, progress_label=None):
		if download_func is not None:
			return download_func(url, config, progress_label, tmpfile)
		return default_download(url, config, progress_label)

	monkeypatch.setattr("fetch.download_and_sha256", wrapper)

	result = process_status(
		status,
		inst,
		api=None,
		db=db,
		config=cfg,
		progress_mode="off",
		status_idx=1,
		total_label="1",
		removed_tracker=removed_tracker,
	)

	tmp_value = tmpfile if return_tmp else None
	return result, tmp_value


def test_safe_parse_created_returns_datetime_for_valid_iso():
	value = "2023-05-01T12:34:56Z"
	result = _safe_parse_created(value)
	assert result == datetime.datetime(2023, 5, 1, 12, 34, 56, tzinfo=datetime.timezone.utc)


def test_safe_parse_created_returns_none_on_empty_or_none():
	assert _safe_parse_created(None) is None
	assert _safe_parse_created("") is None


def test_safe_parse_created_returns_none_for_invalid_format():
	assert _safe_parse_created("not-a-date") is None


def test_guess_extension_uses_remote_url_suffix_case_insensitive():
	media = {"remote_url": "https://cdn.example/path/IMAGE.PNG"}
	assert _guess_extension(media) == "png"


def test_guess_extension_falls_back_to_media_type_suffix():
	media = {"remote_url": "", "type": "video/mp4"}
	assert _guess_extension(media) == "mp4"


def test_guess_extension_defaults_to_png_for_unknown_image():
	media = {"type": "image"}
	assert _guess_extension(media) == "png"


def test_process_status_keep_old_logs_duplicate_younger(monkeypatch, tmp_path):
	cfg = _make_config(tmp_path)
	cfg.archive.policy = "keep_old"
	inst = InstanceConfig(
		name="inst",
		base_url="https://example",
		access_token="token",
	)
	existing = {
		"sha256": "abc123",
		"created_at": "2023-01-01T00:00:00Z",
		"filepath": str(tmp_path / "existing.png"),
	}
	db = DummyDB(existing)

	status = make_status(created_at="2023-01-02T00:00:00Z")

	_run_process_status(status, inst, db, cfg, monkeypatch, tmp_path)

	assert db.logged
	assert db.logged[0]["reason"] == "duplicate_younger"
	assert not db.set_calls


def test_process_status_latest_logs_duplicate_newer(monkeypatch, tmp_path):
	cfg = _make_config(tmp_path)
	cfg.archive.policy = "latest"
	inst = InstanceConfig(
		name="inst",
		base_url="https://example",
		access_token="token",
	)
	existing = {
		"sha256": "abc123",
		"created_at": "2023-01-01T00:00:00Z",
		"filepath": str(tmp_path / "existing.png"),
	}
	db = DummyDB(existing)

	status = make_status(created_at="2023-01-02T00:00:00Z")

	_run_process_status(status, inst, db, cfg, monkeypatch, tmp_path)

	assert db.logged
	assert db.logged[0]["reason"] == "duplicate_newer"
	assert not db.set_calls


def test_process_status_latest_replaces_when_new_status_is_older(monkeypatch, tmp_path):
	cfg = _make_config(tmp_path)
	cfg.archive.policy = "latest"
	inst = InstanceConfig(
		name="inst",
		base_url="https://example",
		access_token="token",
	)
	existing = {
		"sha256": "abc123",
		"created_at": "2023-01-02T00:00:00Z",
		"filepath": str(tmp_path / "existing.png"),
	}
	db = DummyDB(existing)

	status = make_status(created_at="2023-01-01T00:00:00Z")

	calls = []
	def fake_replace(
		existing_record,
		tmpfile,
		status_arg,
		inst_arg,
		config_arg,
		db_arg,
		origin_host,
		origin_group,
		account_host,
		account_group,
	):
		calls.append(
			{
				"existing_created": existing_record["created_at"],
				"status_id": status_arg["id"],
				"tmpfile": tmpfile,
			}
		)
		Path(tmpfile).unlink(missing_ok=True)

	monkeypatch.setattr("fetch.replace_existing", fake_replace)

	_run_process_status(status, inst, db, cfg, monkeypatch, tmp_path)

	assert calls
	assert not db.logged


def test_process_status_logs_duplicate_unknown_when_created_missing(monkeypatch, tmp_path):
	cfg = _make_config(tmp_path)
	inst = InstanceConfig(
		name="inst",
		base_url="https://example",
		access_token="token",
	)
	existing = {
		"sha256": "abc123",
		"created_at": "2023-01-01T00:00:00Z",
		"filepath": str(tmp_path / "existing.png"),
	}
	db = DummyDB(existing)

	status = make_status()
	status["created_at"] = None

	_, tmpfile = _run_process_status(
		status,
		inst,
		db,
		cfg,
		monkeypatch,
		tmp_path,
		return_tmp=True,
	)

	assert db.logged
	assert db.logged[0]["reason"] == "duplicate_unknown"
	assert tmpfile is not None
	assert not tmpfile.exists()


def test_process_status_skip_logs_removed(monkeypatch, tmp_path):
	cfg = _make_config(tmp_path)
	inst = InstanceConfig(
		name="inst",
		base_url="https://example",
		access_token="token",
	)
	status = make_status()

	log_reasons = []
	monkeypatch.setattr(
		"fetch.should_skip",
		lambda status_arg, inst_arg, cfg_arg: (True, "forced_skip"),
	)

	def fake_log_removed(
		db,
		status_arg,
		inst_arg,
		sha256,
		reason,
		origin_host,
		origin_group,
		account_host,
		account_group,
		config,
	):
		log_reasons.append(reason)

	monkeypatch.setattr("fetch.log_removed", fake_log_removed)

	download_called = {"flag": False}

	def download_override(url, config, progress_label, tmpfile):
		download_called["flag"] = True
		raise AssertionError("should not download when skipped")

	_run_process_status(
		status,
		inst,
		db=DummyDB(),
		cfg=cfg,
		monkeypatch=monkeypatch,
		tmp_path=tmp_path,
		download_func=download_override,
	)

	assert log_reasons == ["forced_skip"]
	assert download_called["flag"] is False


def test_process_status_logs_media_not_found(monkeypatch, tmp_path):
	cfg = _make_config(tmp_path)
	inst = InstanceConfig(
		name="inst",
		base_url="https://example",
		access_token="token",
	)
	status = make_status()
	db = DummyDB()

	calls = []

	response = requests.Response()
	response.status_code = 404

	def failing_download(url, config, progress_label, tmpfile):
		calls.append(url)
		raise requests.HTTPError(response=response)

	result, _ = _run_process_status(
		status,
		inst,
		db,
		cfg,
		monkeypatch,
		tmp_path,
		download_func=failing_download,
	)

	assert result is False
	assert db.logged
	assert db.logged[0]["reason"] == "media_not_found"
	assert calls == ["https://cdn.example/media/file.png"]


def test_process_status_skips_urls_marked_missing(monkeypatch, tmp_path):
	cfg = _make_config(tmp_path)
	inst = InstanceConfig(
		name="inst",
		base_url="https://example",
		access_token="token",
	)
	status = make_status()
	db = DummyDB()
	tracker = DummyTracker(skipped={"https://cdn.example/media/file.png"})

	def failing_download(url, config, progress_label, tmpfile):
		raise AssertionError("download should not run when tracker skips")

	result, _ = _run_process_status(
		status,
		inst,
		db,
		cfg,
		monkeypatch,
		tmp_path,
		download_func=failing_download,
		removed_tracker=tracker,
	)

	assert result is False
	assert not db.logged


def test_process_status_records_media_not_found_in_tracker(monkeypatch, tmp_path):
	cfg = _make_config(tmp_path)
	inst = InstanceConfig(
		name="inst",
		base_url="https://example",
		access_token="token",
	)
	status = make_status()
	db = DummyDB()
	tracker = DummyTracker()

	response = requests.Response()
	response.status_code = 404

	def failing_download(url, config, progress_label, tmpfile):
		raise requests.HTTPError(response=response)

	_run_process_status(
		status,
		inst,
		db,
		cfg,
		monkeypatch,
		tmp_path,
		download_func=failing_download,
		removed_tracker=tracker,
	)

	assert tracker.recorded == ["https://cdn.example/media/file.png"]


def test_log_removed_records_entry_when_not_dry_run():
	cfg = GlobalConfig()
	inst = InstanceConfig(
		name="inst",
		base_url="https://example",
		access_token="token",
	)
	status = make_status()
	db = DummyDB()

	log_removed(
		db,
		status,
		inst,
		sha256="deadbeef",
		reason="duplicate",
		origin_host="cdn.example",
		origin_group="example",
		account_host="example.social",
		account_group="example",
		config=cfg,
	)

	assert len(db.logged) == 1
	entry = db.logged[0]
	assert entry["sha256"] == "deadbeef"
	assert entry["reason"] == "duplicate"
	assert entry["instance_label"] == "inst"
	assert entry["origin_group"] == "example"


def test_removed_media_tracker_skips_recent_entries(tmp_path):
	removed_path = tmp_path / "removed.jsonl"
	entry = {
		"time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
		"reason": "media_not_found",
		"media_urls": ["https://cdn.example/media/file.png"],
	}
	removed_path.write_text(json.dumps(entry) + "\n", encoding="utf-8")

	tracker = RemovedMediaTracker(removed_path, 3600)
	assert tracker.should_skip("https://cdn.example/media/file.png") is True
	assert tracker.should_skip("https://cdn.example/media/other.png") is False


def test_removed_media_tracker_ignores_old_entries(tmp_path):
	removed_path = tmp_path / "removed.jsonl"
	entry = {
		"time": "2010-01-01T00:00:00+00:00",
		"reason": "media_not_found",
		"media_urls": ["https://cdn.example/media/file.png"],
	}
	removed_path.write_text(json.dumps(entry) + "\n", encoding="utf-8")

	tracker = RemovedMediaTracker(removed_path, 60)
	assert tracker.should_skip("https://cdn.example/media/file.png") is False


def test_log_removed_skips_when_dry_run():
	cfg = GlobalConfig()
	cfg.runtime.dry_run = True
	inst = InstanceConfig(
		name="inst",
		base_url="https://example",
		access_token="token",
	)
	status = make_status()
	db = DummyDB()

	log_removed(
		db,
		status,
		inst,
		sha256="deadbeef",
		reason="duplicate",
		origin_host="cdn.example",
		origin_group="example",
		account_host="example.social",
		account_group="example",
		config=cfg,
	)

	assert db.logged == []


def test_log_download_appends_jsonl(tmp_path, monkeypatch):
	cfg = _make_config(tmp_path)
	inst = InstanceConfig(
		name="inst",
		base_url="https://example",
		access_token="token",
	)
	cfg.paths.logs = tmp_path / "logs"
	status = make_status()

	log_download(
		status,
		inst,
		filepath=cfg.paths.download / "example.png",
		sha256="abc123",
		size=42,
		config=cfg,
		origin_host="cdn.example",
		origin_group="example",
		account_host="example.social",
		account_group="example",
	)

	log_path = build_log_path(status, inst, cfg)
	assert log_path.exists()
	lines = log_path.read_text(encoding="utf-8").splitlines()
	assert len(lines) == 1
	import json
	entry = json.loads(lines[0])
	assert entry["sha256"] == "abc123"
	assert entry["instance_label"] == "inst"


def test_log_download_skips_when_dry_run(tmp_path):
	cfg = _make_config(tmp_path)
	cfg.runtime.dry_run = True
	inst = InstanceConfig(
		name="inst",
		base_url="https://example",
		access_token="token",
	)
	status = make_status()
	cfg.paths.logs = tmp_path / "logs"

	log_download(
		status,
		inst,
		filepath=cfg.paths.download / "example.png",
		sha256="abc123",
		size=42,
		config=cfg,
		origin_host="cdn.example",
		origin_group="example",
		account_host="example.social",
		account_group="example",
	)

	assert not any(cfg.paths.logs.rglob("*.jsonl"))
