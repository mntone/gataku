from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from classify import (
	classify_origin_host,
	classify_origin_group,
	classify_account_host,
	classify_account_group,
)
from config import GlobalConfig, InstanceConfig
from util import parse_time


def _date_vars(created: datetime) -> Dict[str, Any]:
	"""Return common date/time components for template expansions."""
	week = created.isocalendar().week
	quarter = ((created.month - 1) // 3) + 1
	half = 1 if created.month <= 6 else 2
	return {
		"year": created.strftime("%Y"),
		"yearmonth": created.strftime("%Y%m"),
		"date": created.strftime("%Y-%m-%d"),
		"month": created.strftime("%m"),
		"week": f"{week:02d}",
		"quarter": quarter,
		"half": half,
		"yearweek": f"{created.strftime('%Y')}W{week:02d}",
		"yearquarter": f"{created.strftime('%Y')}Q{quarter}",
		"yearhalf": f"{created.strftime('%Y')}H{half}",
		"datetime": created.strftime("%Y%m%d%H%M%S"),
	}


def _default_log_pattern(freq: str) -> str:
	"""
	Return the default log filename template for the requested frequency.
	Frequency can be day/week/month/quarter/year (with common aliases).
	"""
	f = (freq or "month").lower()
	if f in ("day", "daily"):
		return "{origin_group}/{yearmonth}/{date}.jsonl"
	if f in ("week", "weekly"):
		return "{origin_group}/{yearweek}.jsonl"
	if f in ("quarter", "quarterly"):
		return "{origin_group}/{yearquarter}.jsonl"
	if f in ("half", "semester", "semiannual"):
		return "{origin_group}/{yearhalf}.jsonl"
	if f in ("year", "annual"):
		return "{origin_group}/{year}.jsonl"
	return "{origin_group}/{yearmonth}.jsonl"


def format_template(template: str, vars: Dict[str, Any]) -> str:
	"""
	Very small template engine:
	- Replaces {key} with vars[key]
	- Supports partial: {sha256:8} → prefix first 8 chars
	- Leaves unknown keys untouched
	"""

	out = template

	for key, val in vars.items():
		# Basic replacement
		out = out.replace(f"{{{key}}}", str(val))

		# Partial prefix support (e.g., {sha256:8})
		if isinstance(val, str):
			# find all occurrences of {key:N}
			for n in range(1, 65):
				tag = f"{{{key}:{n}}}"
				if tag in out:
					out = out.replace(tag, val[:n])

	return out



def build_filepath(
	status: Dict[str, Any],
	inst: InstanceConfig | None,
	index: int,
	ext: str,
	config: GlobalConfig,
	sha256: str,
	origin_host: str,
	origin_group: str,
	account_host: str,
	account_group: str,
) -> Path:
	"""
	Build output file path based on template.

	Example default pattern:
		"{origin_group}/{yearmonth}/{screenname}-{datetime}-{index}.{ext}"
	"""

	created = parse_time(status["created_at"])

	screenname = ""
	acct = status.get("account") or {}
	if acct:
		screenname = acct.get("username") or acct.get("acct") or ""

	# Formatable variables
	vars = {
		# classification
		"origin_host": origin_host,
		"origin_group": origin_group,
		"account_host": account_host,
		"account_group": account_group,

		# metadata
		"sha256": sha256,
		"screenname": screenname,
		"index": index,
		"ext": ext,
	}

	vars.update(_date_vars(created))

	# pattern from config or default
	tmpl = getattr(config.download, "filename_pattern", None) or \
		"{origin_group}/{yearmonth}/{screenname}-{datetime}-{index}.{ext}"

	rel = format_template(tmpl, vars)

	return Path(config.paths.download) / rel



def build_log_path(
	status: Dict[str, Any],
	inst: InstanceConfig | None,
	config: GlobalConfig,
) -> Path:
	"""
	Build log path based on logging configuration.
	"""

	media = (status.get("media_attachments") or [{}])[0]
	url = media.get("remote_url") or media.get("url")

	if url:
		origin_host = classify_origin_host(url)
		origin_group = classify_origin_group(origin_host)
	else:
		origin_host = "unknown"
		origin_group = "unknown"

	account_host = classify_account_host(status)
	account_group = classify_account_group(account_host)

	created = parse_time(status["created_at"])

	vars = {
		# classification
		"origin_host": origin_host,
		"origin_group": origin_group,
		"account_host": account_host,
		"account_group": account_group,
	}

	vars.update(_date_vars(created))

	log_cfg = getattr(config, "logging", None)
	pattern = None
	frequency = "month"

	if log_cfg:
		pattern = getattr(log_cfg, "filename_pattern", None)
		frequency = getattr(log_cfg, "frequency", frequency)

	base_dir = getattr(config.paths, "logs", Path("logs"))

	tmpl = pattern or _default_log_pattern(frequency)
	rel = format_template(tmpl, vars)

	return Path(base_dir) / rel


def build_tmp_path(sha256: str, config: GlobalConfig) -> Path:
	"""
	Temporary download path.
	Using sha256 prefix to avoid collisions.
	"""

	prefix = sha256[:16]
	return Path(config.paths.tmp) / f"{prefix}.tmp"
