from typing import Dict, Any
from urllib.parse import urlparse

from config import GlobalConfig, InstanceConfig


IMAGE_EXTENSIONS = {
	".png",
	".jpg",
	".jpeg",
	".gif",
	".bmp",
	".webp",
	".heic",
	".avif",
}


def _looks_like_image(media: Dict[str, Any]) -> bool:
	"""Heuristic check to treat unknown media as images based on URL extension."""
	url = media.get("remote_url") or media.get("url") or ""
	if not url:
		return False
	path = urlparse(url).path.lower()
	return any(path.endswith(ext) for ext in IMAGE_EXTENSIONS)


def should_skip(status: Dict[str, Any], inst: InstanceConfig, config: GlobalConfig) -> tuple[bool, str | None]:
	"""
	Return (True, reason) when a status should be skipped.
	"""

	filter_cfg = config.download.filter

	# Skip posts authored by the configured account when include_self is false.
	if not filter_cfg.include_self:
		account = status.get("account") or {}
		account_id = account.get("id")

		if inst.account_id and account_id is not None and str(account_id) == str(inst.account_id):
			return True, "self_post"

		handle = inst.account_handle
		if handle:
			target = handle.lstrip("@").lower()
			candidates = set()
			acct = account.get("acct")
			username = account.get("username")
			if acct:
				candidates.add(acct.lstrip("@").lower())
			if username:
				candidates.add(username.lstrip("@").lower())
			if target in candidates:
				return True, "self_post"

	media = status.get("media_attachments") or []
	if not media:
		return True, "no_media"

	types = set()
	for m in media:
		mtype = m.get("type")
		if isinstance(mtype, str):
			mtype = mtype.lower()
		if filter_cfg.try_unknown_media and (mtype is None or mtype in {"unknown", "other", ""}):
			# When enabled, treat unknown media that look like image URLs as images.
			if _looks_like_image(m):
				mtype = "image"
		types.add(mtype)

	if not filter_cfg.include_gifv and "gifv" in types:
		return True, "gifv_media"

	non_image_types = {t for t in types if t not in {None, "image"}}

	if "audio" in non_image_types:
		if not filter_cfg.include_audio:
			return True, "audio_media"
		non_image_types.remove("audio")

	if non_image_types and not filter_cfg.include_video:
		return True, "non_image_media"

	if not filter_cfg.include_thumbnail_only and not all(m.get("remote_url") for m in media):
		return True, "no_remote_url"

	if not filter_cfg.include_nsfw and status.get("sensitive"):
		return True, "nsfw_filtered"

	return False, None
