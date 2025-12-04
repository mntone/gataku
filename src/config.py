from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
import yaml

from humanfriendly import parse_timespan


_RATE_PATTERN = re.compile(
	r"^\s*(?P<count>[\d\.]+)\s*(?:/|per\s+)(?P<period>.+?)\s*$",
	re.IGNORECASE,
)

DEFAULT_USER_AGENT = "gataku/1.0 (+https://github.com/mntone/gataku)"
_OFF_SENTINELS = {"off"}  # extendable if more disable keywords are introduced


def _ensure_quantity_expression(expr: str) -> str:
	"""Add a default quantity when a human-friendly duration is missing one."""
	expr = expr.strip()
	if not expr:
		raise ValueError("empty delay expression")
	if any(ch.isdigit() for ch in expr):
		return expr
	return f"1 {expr}"


def _parse_delay_value(value: str | int | float) -> float:
	"""
	Parse a human-friendly delay specification.
	Supported forms:
	- numeric seconds (int/float)
	- strings like "5 seconds", "2 minutes"
	- rate expressions like "2/minute" (events per unit)
	"""

	if isinstance(value, (int, float)):
		if value <= 0:
			raise ValueError("delay must be positive")
		return float(value)

	if isinstance(value, str):
		text = value.strip()
		if not text:
			raise ValueError("empty delay string")

		match = _RATE_PATTERN.match(text)
		if match:
			count = float(match.group("count"))
			if count <= 0:
				raise ValueError("rate count must be positive")
			period_expr = _ensure_quantity_expression(match.group("period"))
			period_seconds = parse_timespan(period_expr)
			return period_seconds / count

		return parse_timespan(_ensure_quantity_expression(text))

	raise TypeError(f"Unsupported delay value type: {type(value)!r}")


def _parse_optional_delay(value) -> float | None:
	"""
	Parse a delay duration that can be disabled by setting the value
	to falsy markers like "off" or 0.
	"""
	if value is None:
		return None
	if isinstance(value, bool):
		if value:
			raise ValueError("Boolean true is not a valid duration")
		return None
	if isinstance(value, (int, float)):
		if value <= 0:
			return None
		return _parse_delay_value(value)
	if isinstance(value, str):
		text = value.strip()
		if not text:
			return None
		if text.lower() in _OFF_SENTINELS:
			return None
		return _parse_delay_value(text)
	raise TypeError(f"Unsupported skip duration type: {type(value)!r}")


def _parse_rate_per_minute(value: str | int | float) -> float:
	"""
	Normalize a rate specification into events per minute.

	Accepts numeric values (interpreted as per-minute), strings like
	\"2/minute\", or human-friendly forms understood by `parse_timespan`.
	Raises ValueError for empty or non-positive inputs.
	"""
	if isinstance(value, (int, float)):
		val = float(value)
		if val <= 0:
			raise ValueError("rate must be positive")
		return val

	if isinstance(value, str):
		text = value.strip()
		if not text:
			raise ValueError("empty rate string")

		match = _RATE_PATTERN.match(text)
		if match:
			count = float(match.group("count"))
			if count <= 0:
				raise ValueError("rate count must be positive")
			period_expr = _ensure_quantity_expression(match.group("period"))
			period_seconds = parse_timespan(period_expr)
			if period_seconds <= 0:
				raise ValueError("period must be positive")
			per_second = count / period_seconds
			return per_second * 60.0

		return _parse_rate_per_minute(float(text))

	raise TypeError(f"Unsupported rate value type: {type(value)!r}")


###############################################################################
# Per-instance configuration
###############################################################################

@dataclass
class InstanceConfig:
	"""
	A Mastodon/Misskey instance to fetch bookmarks from.
	"""

	name: str                           # identifier
	base_url: str                       # instance URL
	access_token: str                   # API key/token
	account_id: str | None = None       # local account id for skip_self
	account_handle: str | None = None   # username/@user@host for skip_self

	# optional override post actions
	unbookmark_override: bool | None = None

	# optional override rate limit (posts/minute)
	rate_override: float | None = None


###############################################################################
# Path configuration
###############################################################################

@dataclass
class PathConfig:
	download: Path = Path("data")
	logs: Path = Path("logs")
	tmp: Path = Path("tmp")
	archive: Path = Path("archive")     # folder where replaced duplicates go
	hashdb_file: Path = Path("hashdb.jsonl")
	removed_log_file: Path = Path("removed.jsonl")


###############################################################################
# Rate limit config
###############################################################################

@dataclass
class RateLimitConfig:
	delay_seconds: float = 30.0         # seconds per post
	burst_allowed: bool = False         # allow bursts or strict spacing

	def set_override_rate(self, value: str | int | float):
		"""
		Update delay_seconds based on an explicit posts-per-minute override.
		The override can be specified using the same syntax accepted by
		`_parse_rate_per_minute`.
		"""
		ppm = _parse_rate_per_minute(value)
		self.delay_seconds = 60.0 / max(ppm, 0.01)


###############################################################################
# Download config
###############################################################################

@dataclass
class ContentFilterConfig:
	include_audio: bool = False
	include_gifv: bool = False
	include_nsfw: bool = False
	try_unknown_media: bool = False
	include_self: bool = False
	include_thumbnail_only: bool = False
	include_video: bool = False

@dataclass
class DownloadRetryConfig:
	max_attempts: int = 3
	delay_seconds: float = 2.0
	rate_control: bool = True

@dataclass
class DownloadConfig:
	filename_pattern: str = "{origin_group}/{yearmonth}/{screenname}-{datetime}-{index}.{ext}"
	progress_level: str = "off"        # off / count / filesize
	filter: ContentFilterConfig = field(default_factory=ContentFilterConfig)
	rate: RateLimitConfig = field(default_factory=RateLimitConfig)
	retry: DownloadRetryConfig = field(default_factory=DownloadRetryConfig)
	user_agent: str = DEFAULT_USER_AGENT


###############################################################################
# Archive policy (duplicate handling)
###############################################################################

@dataclass
class ArchivePolicyConfig:
	enabled: bool = True                # archive files instead of deleting
	policy: str = "keep_old"            # keep_old / latest / database
	log_duplicates: bool = True         # record duplicate entries in logs


###############################################################################
# Logging config
###############################################################################

@dataclass
class LoggingConfig:
	frequency: str = "month"
	filename_pattern: str | None = None
	log_removed: bool = True            # log discarded media
	log_duplicate: bool = True          # log duplicate events


###############################################################################
# Removed media handling
###############################################################################

@dataclass
class RemovedLogConfig:
	skip_media_not_found_for: float | None = None


###############################################################################
# Runtime flags
###############################################################################

@dataclass
class RuntimeConfig:
	dry_run: bool = False
	limit: int | None = None
	unbookmark: bool = True
	dump_bookmarks: bool = False


###############################################################################
# Global config root
###############################################################################

@dataclass
class GlobalConfig:
	paths: PathConfig = field(default_factory=PathConfig)
	download: DownloadConfig = field(default_factory=DownloadConfig)
	filter: ContentFilterConfig = field(default_factory=ContentFilterConfig)
	archive: ArchivePolicyConfig = field(default_factory=ArchivePolicyConfig)
	logging: LoggingConfig = field(default_factory=LoggingConfig)
	removed: RemovedLogConfig = field(default_factory=RemovedLogConfig)
	runtime: RuntimeConfig = field(default_factory=RuntimeConfig)

	# multiple server configs
	instances: list[InstanceConfig] = field(default_factory=list)

	config_file: Path | None = None


###############################################################################
# Loader
###############################################################################

def load_config(path: str | Path) -> GlobalConfig:
	"""
	Read a YAML configuration file and return a populated GlobalConfig.

	The loader handles nested sections (paths, download, archive, runtime,
	logging, instances, etc.) and performs the necessary parsing/validation
	for duration and rate expressions.
	"""
	p = Path(path)
	if not p.exists():
		raise FileNotFoundError(f"Config file not found: {p}")

	with p.open("r", encoding="utf-8") as f:
		raw = yaml.safe_load(f) or {}

	cfg = GlobalConfig()
	cfg.config_file = p

	# --- paths --------------------------------------------------------
	if "paths" in raw:
		r = raw["paths"]
		for key in ("download", "logs", "tmp", "archive"):
			if key in r:
				setattr(cfg.paths, key, Path(r[key]))
		if "hashdb_file" in r:
			cfg.paths.hashdb_file = Path(r["hashdb_file"])
		if "removed_log_file" in r:
			cfg.paths.removed_log_file = Path(r["removed_log_file"])

	# --- download -----------------------------------------------------
	if "download" in raw:
		r = raw["download"]
		cfg.download.filename_pattern = r.get(
			"filename_pattern",
			cfg.download.filename_pattern,
		)
		cfg.download.progress_level = r.get("progress", cfg.download.progress_level)
		if "useragent" in r:
			cfg.download.user_agent = r["useragent"]

		if "retry" in r:
			rr = r["retry"]
			cfg.download.retry.max_attempts = rr.get(
				"max_attempts",
				cfg.download.retry.max_attempts,
			)
			delay_val = rr.get("delay")
			if delay_val is not None:
				cfg.download.retry.delay_seconds = _parse_delay_value(delay_val)
			cfg.download.retry.rate_control = rr.get(
				"rate_control",
				cfg.download.retry.rate_control,
			)

		if "rate" in r:
			raw_rate = r["rate"]
			if isinstance(raw_rate, dict):
				rate_value = raw_rate.get("default_rate")
				delay_value = raw_rate.get("delay")
				if rate_value is not None and delay_value is not None:
					raise ValueError("rate.default_rate and rate.delay are mutually exclusive")

				cfg.download.rate.burst_allowed = raw_rate.get(
					"burst_allowed",
					cfg.download.rate.burst_allowed,
				)

				if delay_value is not None:
					cfg.download.rate.delay_seconds = _parse_delay_value(delay_value)
				elif rate_value is not None:
					ppm = _parse_rate_per_minute(rate_value)
					cfg.download.rate.delay_seconds = 60.0 / max(ppm, 0.01)
			else:
				cfg.download.rate.delay_seconds = _parse_delay_value(raw_rate)

		if "includes" in r:
			includes = r["includes"]
			if isinstance(includes, dict):
				alias_map = {
					"gifv": "include_gifv",
					"video": "include_video",
					"audio": "include_audio",
					"thumbnail_only": "include_thumbnail_only",
					"self": "include_self",
					"nsfw": "include_nsfw",
					"try_unknown": "try_unknown_media",
				}
				for key, val in includes.items():
					attr = alias_map.get(key, key)
					if attr in vars(cfg.download.filter):
						setattr(cfg.download.filter, attr, val)

	# --- archive policy ------------------------------------------------
	if "archive" in raw:
		r = raw["archive"]
		cfg.archive.enabled = r.get("enabled", cfg.archive.enabled)
		cfg.archive.policy = r.get("policy", cfg.archive.policy)
		cfg.archive.log_duplicates = r.get("log_duplicates", cfg.archive.log_duplicates)

	# --- logging ------------------------------------------------------
	if "logging" in raw:
		r = raw["logging"]
		if "frequency" in r:
			cfg.logging.frequency = r["frequency"]
		if "filename_pattern" in r:
			cfg.logging.filename_pattern = r["filename_pattern"]
		for key in ("log_removed", "log_duplicate"):
			if key in r:
				setattr(cfg.logging, key, r[key])

	# --- removed handling ---------------------------------------------
	if "removed" in raw:
		r = raw["removed"]
		if "skip_media_not_found" in r:
			cfg.removed.skip_media_not_found_for = _parse_optional_delay(r["skip_media_not_found"])

	# --- runtime ------------------------------------------------------
	if "runtime" in raw:
		r = raw["runtime"]
		cfg.runtime.dry_run = r.get("dry_run", cfg.runtime.dry_run)
		cfg.runtime.limit = r.get("limit", cfg.runtime.limit)
		cfg.runtime.unbookmark = r.get("unbookmark", cfg.runtime.unbookmark)

	# --- instances ----------------------------------------------------
	if "instances" in raw:
		insts = []
		for entry in raw["instances"]:
			unbookmark_override = None
			if "unbookmark_override" in entry:
				unbookmark_override = entry["unbookmark_override"]
			elif "unbookmark" in entry:
				unbookmark_override = entry["unbookmark"]

			post_rate = None
			if "rate_override" in entry:
				post_rate = entry["rate_override"]
			elif "rate" in entry:
				post_rate = entry["rate"]

			if post_rate is not None:
				post_rate = _parse_rate_per_minute(post_rate)

			insts.append(
				InstanceConfig(
					name=entry["name"],
					base_url=entry["base_url"],
					access_token=entry["access_token"],
					account_id=entry.get("account_id"),
					account_handle=entry.get("account_handle") or entry.get("account_screen_name"),
					unbookmark_override=unbookmark_override,
					rate_override=post_rate,
				)
			)
		cfg.instances = insts

	return cfg


###############################################################################
# Directory preparation
###############################################################################

def ensure_dirs(cfg: GlobalConfig):
	"""
	Create required directories (unless dry-run).
	"""

	if cfg.runtime.dry_run:
		return

	dirs = {
		cfg.paths.archive,
		cfg.paths.download,
		cfg.paths.logs,
		cfg.paths.tmp,
	}

	for p in dirs:
		p.mkdir(parents=True, exist_ok=True)
