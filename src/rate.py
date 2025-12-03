import time

from config import GlobalConfig


def rate_sleep(config: GlobalConfig):
	"""
	Sleep for the currently configured download delay.

	This helper centralizes the rate-control delay so future logic
	(e.g., jitter) can be added in one place.
	"""
	time.sleep(config.download.rate.delay_seconds)
