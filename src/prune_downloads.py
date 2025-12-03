#!/usr/bin/env python3
"""
Utility to delete downloaded files (relative to download root)
and remove their entries from hashdb.jsonl.
"""

import argparse
from pathlib import Path
import sys

from config import load_config
from hashdb import JsonlHashDB


def _normalize_target(download_root: Path, spec: str) -> Path:
	"""
	Resolve user-supplied path specs into absolute paths under download_root.
	Rejects attempts to target the root itself or to escape the download tree.
	"""
	raw = Path(spec)
	if raw.is_absolute():
		target = raw
	else:
		target = download_root / raw
	target = target.expanduser().resolve(strict=False)

	root = download_root.expanduser().resolve(strict=False)
	if root == target:
		raise ValueError("cannot target the download root itself")
	if root not in target.parents:
		raise ValueError(f"target {spec} is outside download directory {download_root}")

	return target


def main():
	"""Entry point for the prune-downloads CLI utility."""
	parser = argparse.ArgumentParser(
		description="Remove downloaded files and matching hashdb entries."
	)
	parser.add_argument(
		"--config",
		default="config.yaml",
		help="Path to configuration file (default: config.yaml)",
	)
	parser.add_argument(
		"paths",
		nargs="+",
		help="Paths under the download directory (e.g. misskey/foo.png)",
	)

	args = parser.parse_args()

	try:
		config = load_config(args.config)
	except Exception as exc:
		print(f"[ERROR] Failed to load config: {exc}")
		return 1

	download_root = Path(config.paths.download)
	db = JsonlHashDB(
		path=config.paths.hashdb_file,
		removed_path=config.paths.removed_log_file,
	)

	try:
		targets = [
			_normalize_target(download_root, spec)
			for spec in args.paths
		]
	except ValueError as exc:
		print(f"[ERROR] {exc}")
		return 1

	# deduplicate while preserving order
	seen = set()
	unique_targets = []
	for t in targets:
		if t in seen:
			continue
		seen.add(t)
		unique_targets.append(t)

	removed_entries = db.delete_by_filepaths(unique_targets)
	if removed_entries:
		print(f"[INFO] Removed {len(removed_entries)} entries from hashdb")
	else:
		print("[WARN] No matching hashdb entries were found")

	deleted_files = 0
	missing_files = 0
	for target in unique_targets:
		try:
			target.unlink()
			print(f"[OK] Deleted file: {target}")
			deleted_files += 1
		except FileNotFoundError:
			print(f"[WARN] File not found (hashdb entry removed if existed): {target}")
			missing_files += 1

	print(f"[DONE] Files deleted: {deleted_files}, missing: {missing_files}")
	return 0


if __name__ == "__main__":
	sys.exit(main())
