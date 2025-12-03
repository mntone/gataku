#!/usr/bin/env python3
import sys
import traceback
import argparse

from config import load_config, GlobalConfig, InstanceConfig
from hashdb import JsonlHashDB
from fetch import run_all
from api import APIFactory


def parse_args():
	"""
	Build and parse the CLI for the main fetcher binary.

	Returns:
		argparse.Namespace describing config path, runtime limits, rate
		overrides, dry-run flags, and other command toggles.
	"""
	p = argparse.ArgumentParser(
		description="Fediverse image archiver"
	)

	p.add_argument(
		"--config",
		default="config.yaml",
		help="Path to config file"
	)

	p.add_argument(
		"--limit",
		type=int,
		default=None,
		help="Limit number of statuses to process"
	)

	p.add_argument(
		"--unbookmark",
		action="store_true",
		help="Force unbookmark enabled"
	)

	p.add_argument(
		"--no-unbookmark",
		action="store_true",
		help="Force unbookmark disabled"
	)

	p.add_argument(
		"--rate",
		type=str,
		default=None,
		help="Override rate, e.g. '2/minute' or '1.5/hour'",
	)

	p.add_argument(
		"--dry-run",
		action="store_true",
		help="Do not write files or modify bookmarks"
	)


	p.add_argument(
		"--dump-bookmarks",
		action="store_true",
		help="Print raw bookmark JSON objects for debugging",
	)

	return p.parse_args()


def apply_overrides(config: GlobalConfig, args: argparse.Namespace) -> None:
	"""
	Override config using CLI flags
	"""

	if args.limit is not None:
		print(f"[CLI] override limit: {args.limit}")
		config.runtime.limit = args.limit

	if args.rate is not None:
		print(f"[CLI] override rate: {args.rate}")
		config.download.rate.set_override_rate(args.rate)

	# unbookmark
	if args.unbookmark:
		print("[CLI] override unbookmark: TRUE")
		config.runtime.unbookmark = True
		for inst in config.instances:
			inst.unbookmark_override = True

	if args.no_unbookmark:
		print("[CLI] override unbookmark: FALSE")
		config.runtime.unbookmark = False
		for inst in config.instances:
			inst.unbookmark_override = False

	# dry-run (global flag)
	config.runtime.dry_run = args.dry_run
	config.runtime.dump_bookmarks = args.dump_bookmarks


def main():
	"""
	Orchestrate config loading, CLI overrides, hashdb init, API setup,
	and instance processing for the archiver.
	"""
	args = parse_args()

	print("== Fediverse Image Fetcher ==")

	# load config
	try:
		config = load_config(args.config)
		print(f"[OK] Loaded config from {args.config}")
	except Exception as e:
		print(f"[ERROR] Failed to load config: {e}")
		traceback.print_exc()
		sys.exit(1)

	# CLI overrides
	apply_overrides(config, args)

	# initialize DB (skip if dry-run)
	try:
		db = JsonlHashDB(
			path=config.paths.hashdb_file,
			removed_path=config.paths.removed_log_file,
		)
		print(f"[OK] Initialized hashdb: {config.paths.hashdb_file}")
	except Exception as e:
		print(f"[ERROR] Failed to init db: {e}")
		traceback.print_exc()
		sys.exit(1)

	# build API factory wrapper
	def api_factory(inst: InstanceConfig):
		"""Wrapper that builds Mastodon API clients with error logging."""
		try:
			return APIFactory.from_instance(inst, dump_raw=config.runtime.dump_bookmarks)
		except Exception as e:
			print(f"[ERROR] Failed to setup API for {inst.name}: {e}")
			traceback.print_exc()
			return None

	# run
	try:
		run_all(
			instances=config.instances,
			api_factory=api_factory,
			db=db,
			config=config,
		)
	except KeyboardInterrupt:
		print("\n[WARN] Interrupted by user")
	except Exception as e:
		print(f"[ERROR] Fatal: {e}")
		traceback.print_exc()

	print("== Finished ==")


if __name__ == "__main__":
	main()
