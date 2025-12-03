from __future__ import annotations

from typing import Dict, Any, List, Tuple, Optional, Iterator

from urllib.parse import urlparse, parse_qs
import requests

from config import InstanceConfig

USER_AGENT = "gataku/1.0 (+https://github.com/mntone/gataku)"


class MastodonAPI:
	"""
	Simple Mastodon REST client for bookmark operations.
	"""

	def __init__(self, inst: InstanceConfig, dump_raw: bool = False):
		"""
		Create an API wrapper bound to a specific Mastodon instance.

		Args:
			inst: Instance configuration, including URL and token.
			dump_raw: When true, responses are printed to stdout for debugging.
		"""
		self.inst = inst
		self.dump_raw = dump_raw

	def fetch_bookmarks(self) -> Iterator[Dict[str, Any]]:
		"""
		Iterate over all bookmarks for the configured account.
		Handles pagination transparently via the Link header.
		"""
		max_id: Optional[str] = None

		while True:
			data, max_id = self._fetch_bookmarks_page(max_id=max_id)
			if not data:
				break

			for status in data:
				yield status

			if not max_id:
				break

	def delete_bookmark(self, status_id: str):
		"""Remove a bookmark for the given status ID."""
		url = f"{self.inst.base_url}/api/v1/statuses/{status_id}/unbookmark"
		r = requests.post(url, headers=self._auth_headers(), timeout=15)
		r.raise_for_status()

	def _fetch_bookmarks_page(
		self,
		max_id: Optional[str] = None,
		limit: int = 40,
	) -> Tuple[List[Dict[str, Any]], Optional[str]]:
		"""
		Fetch a single bookmarks page.
		Returns (list of statuses, next max_id for pagination).
		"""
		url = f"{self.inst.base_url}/api/v1/bookmarks"
		params: Dict[str, Any] = {"limit": limit}
		if max_id:
			params["max_id"] = max_id

		r = requests.get(url, headers=self._auth_headers(), params=params, timeout=15)
		r.raise_for_status()

		data = r.json()
		if self.dump_raw:
			import json
			import sys
			print(json.dumps(data, ensure_ascii=False))
			sys.stdout.flush()
		next_max_id = self._parse_next_max_id(r.links)

		return data, next_max_id

	def _auth_headers(self) -> Dict[str, str]:
		"""Authorization headers for Mastodon API calls."""
		return {
			"Authorization": f"Bearer {self.inst.access_token}",
			"User-Agent": USER_AGENT,
		}

	@staticmethod
	def _parse_next_max_id(links: Dict[str, Any]) -> Optional[str]:
		"""
		Extract the 'max_id' parameter from a Mastodon pagination link.
		Returns None when no further page is available.
		"""
		next_link = links.get("next")
		if not next_link:
			return None

		href = next_link.get("url") or ""
		qs = parse_qs(urlparse(href).query)
		vals = qs.get("max_id")
		if not vals:
			return None
		return vals[0]
