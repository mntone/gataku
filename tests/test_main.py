from pathlib import Path
import types

import pytest

from config import GlobalConfig, InstanceConfig
from main import apply_overrides, parse_args
from prune_downloads import _normalize_target


def _make_args(**overrides):
	defaults = {
		"limit": None,
		"rate": None,
		"unbookmark": False,
		"no_unbookmark": False,
		"dry_run": False,
		"dump_bookmarks": False,
	}
	defaults.update(overrides)
	return types.SimpleNamespace(**defaults)


def test_apply_overrides_sets_limit_and_rate():
	cfg = GlobalConfig()
	args = _make_args(limit=5, rate="120/minute")

	apply_overrides(cfg, args)

	assert cfg.runtime.limit == 5
	assert cfg.download.rate.delay_seconds == pytest.approx(0.5)


def test_apply_overrides_unbookmark_flags_instances():
	cfg = GlobalConfig()
	cfg.instances = [
		InstanceConfig(name="a", base_url="https://a", access_token="tok"),
		InstanceConfig(name="b", base_url="https://b", access_token="tok"),
	]
	args = _make_args(unbookmark=True)

	apply_overrides(cfg, args)

	assert cfg.runtime.unbookmark is True
	assert all(inst.unbookmark_override is True for inst in cfg.instances)


def test_apply_overrides_no_unbookmark_disables_instances():
	cfg = GlobalConfig()
	cfg.instances = [
		InstanceConfig(name="a", base_url="https://a", access_token="tok"),
	]
	args = _make_args(no_unbookmark=True)

	apply_overrides(cfg, args)

	assert cfg.runtime.unbookmark is False
	assert cfg.instances[0].unbookmark_override is False


def test_apply_overrides_sets_dry_run_and_dump_flags():
	cfg = GlobalConfig()
	args = _make_args(dry_run=True, dump_bookmarks=True)

	apply_overrides(cfg, args)

	assert cfg.runtime.dry_run is True
	assert cfg.runtime.dump_bookmarks is True


def test_normalize_target_accepts_relative_under_root(tmp_path):
	download_root = tmp_path / "downloads"
	(download_root / "foo").mkdir(parents=True)
	(download_root / "foo" / "bar.txt").write_text("data")

	result = _normalize_target(download_root, "foo/bar.txt")

	assert result == (download_root / "foo" / "bar.txt").resolve(strict=False)


def test_normalize_target_rejects_root_itself(tmp_path):
	download_root = tmp_path / "downloads"
	download_root.mkdir()

	with pytest.raises(ValueError, match="cannot target the download root itself"):
		_normalize_target(download_root, str(download_root))


def test_normalize_target_rejects_outside_path(tmp_path):
	download_root = tmp_path / "downloads"
	download_root.mkdir()
	external = tmp_path / "other" / "foo.txt"
	external.parent.mkdir()
	external.write_text("data")

	with pytest.raises(ValueError, match="outside download directory"):
		_normalize_target(download_root, str(external))


def test_parse_args_defaults(monkeypatch):
	monkeypatch.setattr("sys.argv", ["prog"])
	args = parse_args()

	assert args.config == "config.yaml"
	assert args.limit is None
	assert args.unbookmark is False
	assert args.no_unbookmark is False
	assert args.rate is None
	assert args.dry_run is False
	assert args.dump_bookmarks is False


def test_parse_args_parses_overrides(monkeypatch):
	monkeypatch.setattr(
		"sys.argv",
		[
			"prog",
			"--config",
			"custom.yaml",
			"--limit",
			"5",
			"--unbookmark",
			"--rate",
			"10/minute",
			"--dry-run",
			"--dump-bookmarks",
		],
	)
	args = parse_args()

	assert args.config == "custom.yaml"
	assert args.limit == 5
	assert args.unbookmark is True
	assert args.rate == "10/minute"
	assert args.dry_run is True
	assert args.dump_bookmarks is True
