import hashlib
import requests
import time
import tempfile
from typing import Tuple
import sys

from config import GlobalConfig


def download_and_sha256(url: str, config: GlobalConfig, progress_label: str | None = None) -> Tuple[str, str, int]:
	"""
	Download a file with retries and compute its SHA256 hash.
	Returns (tmpfile_path, sha256_hex, size_bytes).
	"""

	attempts = config.download.retry.max_attempts

	last_exc: Exception | None = None

	for i in range(attempts):
		try:
			return _attempt_download(url, config, progress_label)
		except Exception as e:
			last_exc = e
			# Give up immediately if this was the final attempt.
			if i + 1 >= attempts:
				raise

			# Sleep according to rate control or the retry delay.
			if config.download.retry.rate_control:
				time.sleep(config.download.rate.delay_seconds)
			else:
				time.sleep(config.download.retry.delay_seconds)

	# This is normally unreachable because we either return or raise before here.
	if last_exc:
		raise last_exc
	raise RuntimeError("download failed unexpectedly")


def _attempt_download(url: str, cfg: GlobalConfig, progress_label: str | None) -> Tuple[str, str, int]:
	"""Stream a single HTTP download to a temp file, returning path/hash/size."""
	r = requests.get(url, stream=True, timeout=15, headers={"User-Agent": cfg.download.user_agent})
	r.raise_for_status()

	hasher = hashlib.sha256()
	size = 0

	tmp = tempfile.NamedTemporaryFile(delete=False)
	tmp_path = tmp.name

	with tmp as f:
		downloaded = 0
		total = int(r.headers.get("content-length") or 0)
		show_size = (
			progress_label is not None
			and (cfg.download.progress_level or "off").lower() == "filesize"
		)
		last_len = 0
		for chunk in r.iter_content(8192):
			if not chunk:
				continue
			hasher.update(chunk)
			size += len(chunk)
			downloaded += len(chunk)
			f.write(chunk)
			if show_size:
				if total > 0:
					percent = min(downloaded / total, 1.0) * 100
					line = (
						f"{progress_label} "
						f"{_format_bytes(downloaded)}/{_format_bytes(total)} "
						f"({percent:.1f}%)"
					)
				else:
					line = f"{progress_label} {_format_bytes(downloaded)}"
				padding = " " * max(last_len - len(line), 0)
				sys.stdout.write("\r" + line + padding)
				sys.stdout.flush()
				last_len = len(line)
		if show_size:
			if total > 0:
				final = (
					f"{progress_label} "
					f"{_format_bytes(total)}/{_format_bytes(total)} (100.0%)"
				)
			else:
				final = f"{progress_label} {_format_bytes(downloaded)} (done)"
			padding = " " * max(last_len - len(final), 0)
			sys.stdout.write("\r" + final + padding + "\n")
			sys.stdout.flush()

	return tmp_path, hasher.hexdigest(), size


def _format_bytes(size: int) -> str:
	"""Convert a size in bytes into a human-friendly string."""
	thresholds = [
		(1024 ** 3, "GB"),
		(1024 ** 2, "MB"),
		(1024, "KB"),
	]
	for factor, suffix in thresholds:
		if size >= factor:
			value = size / factor
			if value < 10:
				return f"{value:.2f} {suffix}"
			return f"{value:.1f} {suffix}"
	return f"{size} B"
