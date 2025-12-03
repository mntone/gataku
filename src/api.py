"""
Service-agnostic API factory.

Right now only Mastodon-compatible instances are supported, but the
structure allows plugging in other backends later.
"""

from config import InstanceConfig
from interfaces import BookmarksAPI
from mastodon_api import MastodonAPI


class APIFactory:
	@staticmethod
	def from_instance(inst: InstanceConfig, dump_raw: bool = False) -> BookmarksAPI:
		"""
		Build an API client for the given instance.

		Currently always returns a Mastodon-compatible client. When additional
		fediverse backends are supported, this function will detect the instance
		type and return the appropriate implementation.
		"""
		# TODO: detect instance type once multiple backends exist.
		return MastodonAPI(inst, dump_raw=dump_raw)
