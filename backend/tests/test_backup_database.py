import sqlite3

from scripts.backup_database import create_backup, verify_database


def test_sqlite_backup_is_consistent_and_has_checksum(tmp_path):
    source = tmp_path / "source.db"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE media (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
        connection.executemany("INSERT INTO media (name) VALUES (?)", [("Alpha",), ("Beta",)])
        connection.commit()

    result = create_backup(source, tmp_path / "backups", "2026-08-14_120000")
    target = tmp_path / "backups" / "kol_crm_backup_2026-08-14_120000.db"

    assert result["path"] == str(target.resolve())
    assert len(result["sha256"]) == 64
    assert target.with_suffix(".db.sha256").read_text(encoding="ascii").endswith(f"  {target.name}\n")
    assert verify_database(target)["sha256"] == result["sha256"]
    with sqlite3.connect(target) as connection:
        assert connection.execute("SELECT name FROM media ORDER BY id").fetchall() == [("Alpha",), ("Beta",)]
