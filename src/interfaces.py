from __future__ import annotations

from pathlib import Path
from typing import Iterable, Dict, Any, Protocol, Optional


class BookmarksAPI(Protocol):
	def fetch_bookmarks(self) -> Iterable[Dict[str, Any]]:
		"""
		Return an iterable of bookmark status objects.
		Implementations should handle pagination internally.
		"""
		...

	def delete_bookmark(self, status_id: str) -> None:
		"""Remove a bookmark by status ID."""
		...


class HashDB(Protocol):
	def get(self, sha: str) -> Optional[Dict[str, Any]]:
		"""Return the stored entry for the given hash."""
		...

	def set(self, entry: Dict[str, Any]) -> None:
		"""Persist a hash entry."""
		...

	def log_removed(self, entry: Dict[str, Any]) -> None:
		"""Record a removed-media entry."""
		...

	def delete_by_filepaths(self, paths: Iterable[str | Path]) -> Iterable[Dict[str, Any]]:
		"""Delete entries whose filepaths match any of the provided ones."""
		...
