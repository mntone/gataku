from __future__ import annotations

from copy import deepcopy


_DEFAULT_STATUS = {
	"id": "status-1",
	"url": "https://example.social/@user/1",
	"created_at": "2023-01-02T00:00:00Z",
	"account": {
		"id": "acct-1",
		"username": "alice",
		"acct": "alice@example.social",
	},
	"media_attachments": [
		{"type": "image", "remote_url": "https://cdn.example/media/file.png"}
	],
}


def make_status(**overrides) -> dict:
	status = deepcopy(_DEFAULT_STATUS)
	for key, val in overrides.items():
		status[key] = val
	return status
