import json
from pathlib import Path
from typing import Optional, Dict, Any, Iterable, List


class JsonlHashDB:
	def __init__(self, path: Path, removed_path: Path):
		"""Store and query download metadata backed by JSONL files."""
		self.path = path
		self.removed_path = removed_path
		self.entries: Dict[str, Dict[str, Any]] = {}  # sha256 -> entry

		if self.path.exists():
			self._load()

	def _load(self):
		"""Populate the in-memory cache from the on-disk database."""
		with open(self.path, "r", encoding="utf-8") as f:
			for line in f:
				line = line.strip()
				if not line:
					continue
				try:
					obj = json.loads(line)
					sha = obj["sha256"]
					self.entries[sha] = obj
				except Exception:
					# Ignore malformed lines so a corrupt record does not break load.
					continue

	def get(self, sha: str) -> Optional[Dict[str, Any]]:
		"""Return the stored entry for the given sha256 hash, if any."""
		return self.entries.get(sha)

	def set(self, entry: Dict[str, Any]):
		"""Append a new entry to the database and update the cache."""
		sha = entry["sha256"]
		self.entries[sha] = entry
		self.path.parent.mkdir(parents=True, exist_ok=True)
		with open(self.path, "a", encoding="utf-8") as f:
			f.write(json.dumps(entry, ensure_ascii=False) + "\n")

	def log_removed(self, entry: Dict[str, Any]):
		"""Append a record to the removed-log JSONL file."""
		# Entry is expected to include sha256, status metadata, timestamps, etc.
		self.removed_path.parent.mkdir(parents=True, exist_ok=True)
		with open(self.removed_path, "a", encoding="utf-8") as f:
			f.write(json.dumps(entry, ensure_ascii=False) + "\n")

	def _normalize_path(self, value: str | Path) -> str:
		"""Normalize a path to an absolute string for comparison/deduping."""
		return str(Path(value).expanduser().resolve(strict=False))

	def _rewrite_entries(self):
		"""Rewrite the database file with the current in-memory entries."""
		self.path.parent.mkdir(parents=True, exist_ok=True)
		with open(self.path, "w", encoding="utf-8") as f:
			for entry in self.entries.values():
				f.write(json.dumps(entry, ensure_ascii=False) + "\n")

	def delete_by_filepaths(self, paths: Iterable[str | Path]) -> List[Dict[str, Any]]:
		"""Remove entries matching the provided file paths and rewrite disk."""
		targets = {self._normalize_path(p) for p in paths}
		if not targets:
			return []

		removed: List[Dict[str, Any]] = []
		for sha, entry in list(self.entries.items()):
			fp = entry.get("filepath")
			if not fp:
				continue
			if self._normalize_path(fp) in targets:
				removed.append(entry)
				del self.entries[sha]

		if removed:
			self._rewrite_entries()

		return removed
