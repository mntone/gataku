import json

from hashdb import JsonlHashDB


def test_delete_by_filepaths_rewrites_db(tmp_path, monkeypatch):
	db_path = tmp_path / "hashdb.jsonl"
	removed_path = tmp_path / "removed.jsonl"
	download_root = tmp_path / "out" / "downloads"
	download_root.mkdir(parents=True, exist_ok=True)

	entry1 = {
		"sha256": "aaa",
		"filepath": "out/downloads/foo.png",
	}
	entry2 = {
		"sha256": "bbb",
		"filepath": str(download_root / "bar.png"),
	}

	with db_path.open("w", encoding="utf-8") as f:
		f.write(json.dumps(entry1) + "\n")
		f.write(json.dumps(entry2) + "\n")

	db = JsonlHashDB(db_path, removed_path)

	monkeypatch.chdir(tmp_path)

	target = download_root / "foo.png"
	removed = db.delete_by_filepaths([target])

	assert len(removed) == 1
	assert db.get("aaa") is None
	assert db.get("bbb") is not None

	with db_path.open("r", encoding="utf-8") as f:
		lines = [line for line in f.read().splitlines() if line]
	assert len(lines) == 1
	assert json.loads(lines[0])["sha256"] == "bbb"
