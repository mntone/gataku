import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlparse
from typing import Any, Callable, Dict, Iterable

import requests

from classify import (
	classify_origin_host,
	classify_origin_group,
	classify_account_host,
	classify_account_group,
)
from config import GlobalConfig, InstanceConfig
from downloader import download_and_sha256
from filenames import build_filepath, build_log_path
from fileops import move_to_archive
from filters import should_skip
from interfaces import HashDB
from util import parse_time


def _safe_parse_created(value: str | None) -> datetime | None:
	"""
	Try to parse a timestamp into datetime; return None on failure.
	Prevents malformed data from breaking duplicate comparisons.
	"""
	if not value:
		return None
	try:
		return parse_time(value)
	except Exception:
		return None


class RemovedMediaTracker:
	"""
	Track media URLs that recently returned media_not_found to avoid repeats.
	"""

	def __init__(self, removed_path: Path, window_seconds: float | None):
		self.removed_path = removed_path
		self.window_seconds = window_seconds or 0.0
		self.enabled = self.window_seconds > 0
		self._recent: dict[str, datetime] = {}
		if self.enabled:
			self._load_recent_entries()

	def _parse_timestamp(self, value: str | None) -> datetime | None:
		if not value:
			return None
		text = value.replace("Z", "+00:00")
		try:
			ts = datetime.fromisoformat(text)
		except ValueError:
			return None
		# Normalize to timezone-aware UTC for consistent comparisons.
		if ts.tzinfo is None:
			return ts.replace(tzinfo=timezone.utc)
		return ts.astimezone(timezone.utc)

	def _load_recent_entries(self) -> None:
		if not self.removed_path.exists():
			return
		cutoff = datetime.now(timezone.utc) - timedelta(seconds=self.window_seconds)
		with open(self.removed_path, "r", encoding="utf-8") as f:
			for line in f:
				line = line.strip()
				if not line:
					continue
				try:
					entry = json.loads(line)
				except json.JSONDecodeError:
					continue
				if entry.get("reason") != "media_not_found":
					continue
				ts = self._parse_timestamp(entry.get("time"))
				if ts is None or ts < cutoff:
					continue
				for url in entry.get("media_urls") or []:
					if url:
						self._recent[url] = ts

	def should_skip(self, url: str | None) -> bool:
		if not self.enabled or not url:
			return False
		return url in self._recent

	def record(self, urls: Iterable[str]) -> None:
		if not self.enabled:
			return
		now = datetime.now(timezone.utc)
		for url in urls:
			if url:
				self._recent[url] = now


def log_download(
	status: Dict[str, Any],
	inst: InstanceConfig,
	filepath: Path,
	sha256: str,
	size: int,
	config: GlobalConfig,
	origin_host: str,
	origin_group: str,
	account_host: str,
	account_group: str,
) -> None:
	"""Append download log entry to jsonl"""
	media_urls = [
		m.get("remote_url") or m.get("url")
		for m in (status.get("media_attachments") or [])
	]

	record = {
		"time": datetime.now(timezone.utc).isoformat(),
		"filepath": str(filepath),
		"sha256": sha256,
		"size": size,
		"media_urls": media_urls,

		# fediverse info
		"statusid": str(status["id"]),
		"status_url": status.get("url"),
		"created_at": status.get("created_at"),

		# classification
		"origin_host": origin_host,
		"origin_group": origin_group,
		"account_host": account_host,
		"account_group": account_group,

		# instance label (user-defined)
		"instance_label": inst.name,
	}

	if config.runtime.dry_run:
		return

	log_path = build_log_path(status, inst, config)
	log_path.parent.mkdir(parents=True, exist_ok=True)

	with open(log_path, "a", encoding="utf-8") as f:
		f.write(json.dumps(record) + "\n")


def _guess_extension(media: Dict[str, Any]) -> str:
	"""
	Guess a reasonable file extension for a media attachment.
	Prefers URL suffixes; falls back to MIME type or 'png'.
	"""
	source = media.get("remote_url") or media.get("url") or ""
	if source:
		path = urlparse(source).path
		suffix = Path(path).suffix.lower().lstrip(".")
		if suffix:
			return suffix

	mtype = media.get("type") or ""
	if "/" in mtype:
		return mtype.split("/")[-1]
	if mtype and mtype != "image":
		return mtype
	return "png"


def log_removed(
	db: HashDB,
	status: Dict[str, Any],
	inst: InstanceConfig,
	sha256: str | None,
	reason: str | None,
	origin_host: str | None,
	origin_group: str | None,
	account_host: str | None,
	account_group: str | None,
	config: GlobalConfig,
) -> None:
	"""
	Record a discarded media entry in the removal log database.
	Does nothing during dry-run.
	"""
	record = {
		"time": datetime.now(timezone.utc).isoformat(),
		"sha256": sha256,
		"statusid": str(status.get("id")),
		"status_url": status.get("url"),
		"media_urls": [
			m.get("remote_url") or m.get("url")
			for m in (status.get("media_attachments") or [])
		],
		"reason": reason,
		"created_at": status.get("created_at"),

		# classification
		"origin_host": origin_host,
		"origin_group": origin_group,
		"account_host": account_host,
		"account_group": account_group,

		# instance label
		"instance_label": inst.name,
	}

	if not config.runtime.dry_run:
		db.log_removed(record)



def replace_existing(
	existing: Dict[str, Any],
	tmpfile: str,
	status: Dict[str, Any],
	inst: InstanceConfig,
	config: GlobalConfig,
	db: HashDB,
	origin_host: str,
	origin_group: str,
	account_host: str,
	account_group: str,
) -> None:
	"""
	Replace older stored image with newer one.
	existing: record from hashdb
	"""

	old_path = Path(existing["filepath"])

	if not config.runtime.dry_run:
		old_path.parent.mkdir(parents=True, exist_ok=True)

		# move old to archive
		move_to_archive(old_path, config, config.paths.download)

		# replace with new file
		Path(tmpfile).rename(old_path)
	else:
		# discard temp, keep old file
		Path(tmpfile).unlink(missing_ok=True)

	# update record
	existing["created_at"] = status["created_at"]
	existing["filepath"] = str(old_path)

	# preserve classification
	existing["origin_host"] = origin_host
	existing["origin_group"] = origin_group
	existing["account_host"] = account_host
	existing["account_group"] = account_group

	if not config.runtime.dry_run:
		db.set(existing)

	# log replacement result
	log_download(
		status,
		inst,
		old_path,
		existing["sha256"],
		existing.get("size", 0),
		config,
		origin_host,
		origin_group,
		account_host,
		account_group,
	)



def process_status(
	status: Dict[str, Any],
	inst: InstanceConfig,
	api: Any,
	db: HashDB,
	config: GlobalConfig,
	progress_mode: str,
	status_idx: int,
	total_label: str,
	progress_label: str | None = None,
	removed_tracker: RemovedMediaTracker | None = None,
) -> bool:
	"""
	Process a single status
	"""

	# skip rule
	skip, reason = should_skip(status, inst, config)
	if skip:
		if config.logging.log_removed:
			log_removed(
				db,
				status,
				inst,
				sha256=None,
				reason=reason or "filtered",
				origin_host=None,
				origin_group=None,
				account_host=None,
				account_group=None,
				config=config,
			)
		if progress_mode != "off":
			media_urls = [
				m.get("remote_url") or m.get("url")
				for m in (status.get("media_attachments") or [])
			]
			visible_reason = reason or "filtered"
			if media_urls:
				url_info = media_urls[0]
			else:
				url_info = "no media"
			print(f"[{inst.name}] {status_idx}/{total_label} skip {visible_reason}: {url_info}")
		return False

	media_list = status.get("media_attachments") or []

	# account classification (same for whole status)
	account_host = classify_account_host(status)
	account_group = classify_account_group(account_host)

	any_downloaded = False

	for idx, media in enumerate(media_list):

		remote_url = media.get("remote_url") or media.get("url")
		if not remote_url:
			continue

		if removed_tracker and removed_tracker.should_skip(remote_url):
			if progress_mode != "off":
				print(f"[{inst.name}] {status_idx}/{total_label} skip media_not_found_cached: {remote_url}")
			continue

		# origin classification
		origin_host = classify_origin_host(remote_url)
		origin_group = classify_origin_group(origin_host)

		# download
		label = None
		if progress_mode == "filesize" and progress_label:
			label = progress_label.format(idx=idx + 1)
		try:
			tmpfile, sha256, size = download_and_sha256(
				remote_url,
				config,
				progress_label=label,
			)
			any_downloaded = True
		except requests.HTTPError as err:
			status_code = err.response.status_code if err.response is not None else None
			if status_code == 404:
				if removed_tracker:
					removed_tracker.record([remote_url])
				if config.logging.log_removed:
					log_removed(
						db,
						status,
						inst,
						sha256=None,
						reason="media_not_found",
						origin_host=origin_host,
						origin_group=origin_group,
						account_host=account_host,
						account_group=account_group,
						config=config,
					)
				if progress_mode != "off":
					print(f"[{inst.name}] {status_idx}/{total_label} skip media_not_found: {remote_url}")
				continue
			raise

		# check duplicate
		existing = db.get(sha256)

		if existing:
			created_new = _safe_parse_created(status.get("created_at"))
			created_old = _safe_parse_created(existing.get("created_at"))

			if created_new is None or created_old is None or config.archive.policy == "database":
				if config.logging.log_duplicate:
					log_removed(
						db,
						status,
						inst,
						sha256,
						reason="duplicate_unknown",
						origin_host=origin_host,
						origin_group=origin_group,
						account_host=account_host,
						account_group=account_group,
						config=config,
					)
				Path(tmpfile).unlink(missing_ok=True)
				continue

			policy = (config.archive.policy or "keep_old").lower()
			new_is_older = created_new < created_old

			if policy == "keep_old" and not new_is_older:
				if config.logging.log_duplicate:
					log_removed(
						db,
						status,
						inst,
						sha256,
						reason="duplicate_younger",
						origin_host=origin_host,
						origin_group=origin_group,
						account_host=account_host,
						account_group=account_group,
						config=config,
					)
				Path(tmpfile).unlink(missing_ok=True)
				continue

			elif policy == "latest" and not new_is_older:
				if config.logging.log_duplicate:
					log_removed(
						db,
						status,
						inst,
						sha256,
						reason="duplicate_newer",
						origin_host=origin_host,
						origin_group=origin_group,
						account_host=account_host,
						account_group=account_group,
						config=config,
					)
				Path(tmpfile).unlink(missing_ok=True)
				continue

			else:
				replace_existing(
					existing,
					tmpfile,
					status,
					inst,
					config,
					db,
					origin_host,
					origin_group,
					account_host,
					account_group,
				)
				continue

		# new file -> produce destination path
		dst = build_filepath(
			status,
			inst,
			idx,
			ext=_guess_extension(media),
			config=config,
			sha256=sha256,
			origin_host=origin_host,
			origin_group=origin_group,
			account_host=account_host,
			account_group=account_group,
		)

		if not config.runtime.dry_run:
			dst.parent.mkdir(parents=True, exist_ok=True)
			Path(tmpfile).rename(dst)
		else:
			# delete temporary file to avoid leak
			Path(tmpfile).unlink(missing_ok=True)

		# record
		if not config.runtime.dry_run:
			db.set(
				{
					"sha256": sha256,
					"statusid": str(status["id"]),
					"status_url": status.get("url"),
					"instance_label": inst.name,
					"created_at": status["created_at"],
					"filepath": str(dst),
					"size": size,

					# classification
					"origin_host": origin_host,
					"origin_group": origin_group,
					"account_host": account_host,
					"account_group": account_group,
				}
			)

		# log
		log_download(
			status,
			inst,
			dst,
			sha256,
			size,
			config,
			origin_host,
			origin_group,
			account_host,
			account_group,
		)

	return any_downloaded



def run_instance(
	inst: InstanceConfig,
	api: Any,
	db: HashDB,
	config: GlobalConfig,
) -> None:
	"""
	Process bookmarks for a single instance
	"""

	count = 0
	progress_mode = (config.download.progress_level or "off").lower()
	total_label = str(config.runtime.limit) if config.runtime.limit is not None else "∞"

	removed_tracker = RemovedMediaTracker(
		config.paths.removed_log_file,
		config.removed.skip_media_not_found_for,
	)

	for status in api.fetch_bookmarks():
		status_idx = count + 1
		progress_label = None
		if progress_mode == "filesize":
			media_total = len(status.get("media_attachments") or [])
			base_label = f"[{inst.name}] {status_idx}/{total_label} media"
			if media_total > 1:
				progress_label = f"{base_label} {{idx}}/{media_total}"
			else:
				progress_label = base_label
		if progress_mode != "off":
			status_desc = status.get("url") or f"id={status.get('id')}"
			print(f"[{inst.name}] {status_idx}/{total_label} status {status_desc}")

		ok = process_status(
			status,
			inst,
			api,
			db,
			config,
			progress_mode,
			status_idx,
			total_label,
			progress_label=progress_label,
			removed_tracker=removed_tracker,
		)

		delay = config.download.rate.delay_seconds
		if inst.rate_override is not None:
			delay = 60.0 / max(inst.rate_override, 0.01)

		if ok:
			# rate control
			time.sleep(delay)

		count += 1
		if progress_mode == "count":
			print(f"[{inst.name}] {status_idx}/{total_label}")
		if config.runtime.limit and count >= config.runtime.limit:
			break

		# resolve final value
		unbookmark = inst.unbookmark_override
		if unbookmark is None:
			unbookmark = config.runtime.unbookmark

		# optional unbookmark
		if ok and unbookmark and not config.runtime.dry_run:
			api.delete_bookmark(status["id"])



def run_all(
	instances: Iterable[InstanceConfig],
	api_factory: Callable[[InstanceConfig], Any],
	db: HashDB,
	config: GlobalConfig,
) -> None:
	"""
	Iterate all configured instances
	"""

	for inst in instances:
		api = api_factory(inst)
		run_instance(inst, api, db, config)
