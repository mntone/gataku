from datetime import datetime

from config import GlobalConfig
from filenames import (
	build_filepath,
	build_log_path,
	format_template,
	_date_vars,
	_default_log_pattern,
	build_tmp_path,
)
from helpers import make_status


def test_build_filepath_default_pattern(tmp_path):
	cfg = GlobalConfig()
	cfg.paths.download = tmp_path

	status = make_status()
	path = build_filepath(
		status,
		inst=None,
		index=0,
		ext="png",
		config=cfg,
		sha256="abc123",
		origin_host="cdn.example",
		origin_group="example",
		account_host="example.social",
		account_group="example",
	)

	assert path.parent.parent == tmp_path / "example"
	assert path.name.endswith("-0.png")


def test_build_log_path_respects_frequency(tmp_path):
	cfg = GlobalConfig()
	cfg.paths.logs = tmp_path
	cfg.logging.frequency = "week"

	status = make_status()
	path = build_log_path(status, inst=None, config=cfg)

	assert path.parent == tmp_path / "other"
	assert "W" in path.name and path.suffix == ".jsonl"


def test_format_template_handles_prefix_and_missing_keys():
	template = "{username}-{sha256:4}-{missing}"
	result = format_template(template, {"username": "alice", "sha256": "abcdef"})
	assert result == "alice-abcd-{missing}"


def test_date_vars_generate_consistent_components():
	created = datetime(2023, 3, 15, 10, 20, 30)
	vars = _date_vars(created)
	assert vars["year"] == "2023"
	assert vars["yearmonth"] == "202303"
	assert vars["date"] == "2023-03-15"
	assert vars["month"] == "03"
	assert vars["week"] == "11"
	assert vars["quarter"] == 1
	assert vars["half"] == 1
	assert vars["yearweek"].startswith("2023W")
	assert vars["yearquarter"] == "2023Q1"
	assert vars["yearhalf"] == "2023H1"


def test_default_log_pattern_variants():
	assert _default_log_pattern("day") == "{origin_group}/{yearmonth}/{date}.jsonl"
	assert _default_log_pattern("week") == "{origin_group}/{yearweek}.jsonl"
	assert _default_log_pattern("quarter") == "{origin_group}/{yearquarter}.jsonl"
	assert _default_log_pattern("half") == "{origin_group}/{yearhalf}.jsonl"
	assert _default_log_pattern("year") == "{origin_group}/{year}.jsonl"
	assert _default_log_pattern("unknown") == "{origin_group}/{yearmonth}.jsonl"


def test_build_log_path_supports_half_frequency(tmp_path):
	cfg = GlobalConfig()
	cfg.paths.logs = tmp_path
	cfg.logging.frequency = "half"

	status = make_status()
	path = build_log_path(status, inst=None, config=cfg)

	assert path.parent == tmp_path / "other"
	assert path.name == "2023H1.jsonl"


def test_build_tmp_path_uses_sha_prefix(tmp_path):
	cfg = GlobalConfig()
	cfg.paths.tmp = tmp_path
	path = build_tmp_path("abcdef1234567890fedcba", cfg)
	assert path == tmp_path / "abcdef1234567890.tmp"
