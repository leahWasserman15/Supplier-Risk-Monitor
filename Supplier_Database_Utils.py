from contextlib import contextmanager
from pathlib import Path
import sqlite3

import pandas as pd

DEFAULT_DB_PATH = Path(__file__).resolve().with_name("suppliers.db")
DEFAULT_EXCEL_PATH = Path(__file__).resolve().with_name("real_pro_av_companies.xlsx")
TABLE = "vendors"
CHANGES_TABLE = "vendor_changes"
CHANGES_TRIGGER = "vendors_audit_update"
VENDOR_COL = "Company / Brand"


def _quote(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def _sql_literal(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _parse_bool(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(int(value))
    text = str(value).strip().lower()
    if text in {"", "none", "nan"}:
        return None
    if text in {"1", "1.0", "true", "y", "yes"}:
        return True
    if text in {"0", "0.0", "false", "n", "no"}:
        return False
    return None


def _to_sql_value(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, pd.Timestamp):
        return str(value.floor("s"))
    if hasattr(value, "item"):
        try:
            value = value.item()
        except (ValueError, AttributeError):
            pass
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


class CompanyBook:
    def __init__(self, path=DEFAULT_DB_PATH, excel_path=DEFAULT_EXCEL_PATH):
        self.path = Path(path)
        self.excel_path = Path(excel_path)
        if not self.path.exists():
            self._seed_from_excel()
        self._ensure_change_log()
        self._reload()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.path)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _seed_from_excel(self):
        df = pd.read_excel(self.excel_path)
        if "is_risk" in df.columns:
            df["is_risk"] = df["is_risk"].map(_parse_bool)
        columns = [str(c) for c in df.columns]
        col_defs = ", ".join(f"{_quote(c)} TEXT" for c in columns)
        quoted_cols = ", ".join(_quote(c) for c in columns)
        placeholders = ", ".join("?" for _ in columns)
        records = [
            tuple(_to_sql_value(v) for v in row)
            for row in df.itertuples(index=False, name=None)
        ]
        with self._connect() as conn:
            conn.execute(f"DROP TABLE IF EXISTS {TABLE}")
            conn.execute(f"CREATE TABLE {TABLE} ({col_defs})")
            conn.executemany(
                f"INSERT INTO {TABLE} ({quoted_cols}) VALUES ({placeholders})",
                records,
            )

    def _ensure_change_log(self):
        with self._connect() as conn:
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {CHANGES_TABLE} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    changed_at TEXT NOT NULL,
                    vendor TEXT NOT NULL,
                    field TEXT NOT NULL,
                    old_value TEXT,
                    new_value TEXT
                )
                """
            )
            conn.execute(
                f"""
                CREATE INDEX IF NOT EXISTS vendor_changes_vendor_changed_at
                ON {CHANGES_TABLE} (vendor, changed_at)
                """
            )
            columns = [row[1] for row in conn.execute(f"PRAGMA table_info({TABLE})")]
            if not columns:
                return
            vendor_col = VENDOR_COL if VENDOR_COL in columns else columns[0]
            inserts = []
            for col in columns:
                qcol = _quote(col)
                inserts.append(
                    f"""
                    INSERT INTO {CHANGES_TABLE}
                        (changed_at, vendor, field, old_value, new_value)
                    SELECT datetime('now', 'localtime'), NEW.{_quote(vendor_col)},
                           {_sql_literal(col)}, OLD.{qcol}, NEW.{qcol}
                    WHERE OLD.{qcol} IS NOT NEW.{qcol};
                    """
                )
            conn.execute(f"DROP TRIGGER IF EXISTS {CHANGES_TRIGGER}")
            conn.execute(
                f"""
                CREATE TRIGGER {CHANGES_TRIGGER}
                AFTER UPDATE ON {TABLE}
                BEGIN
                {''.join(inserts)}
                END
                """
            )

    def _read_db(self):
        with self._connect() as conn:
            return pd.read_sql_query(f"SELECT * FROM {TABLE}", conn)

    def _reload(self):
        self.df = self._read_db()
        self._prepare()

    def _prepare(self):
        self.df["Last Checked Date"] = pd.to_datetime(
            self.df["Last Checked Date"], errors="coerce"
        )
        self.df["Last Risk Eval"] = pd.to_datetime(
            self.df["Last Risk Eval"], errors="coerce"
        )
        self.df["Risk_level"] = pd.to_numeric(self.df["Risk_level"], errors="coerce")
        # SQLite TEXT / NULL should still accept bools and free-text reasons
        self.df["is_risk"] = self.df["is_risk"].map(_parse_bool).astype(object)
        self.df["Risk_Reason"] = self.df["Risk_Reason"].astype(object)

    def get_vendors(self, run_count):
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT {_quote("Company / Brand")} FROM {TABLE}
                ORDER BY {_quote("Last Checked Date")} ASC
                LIMIT ?
                """,
                (int(run_count),),
            ).fetchall()
        return [row[0] for row in rows]

    def get_risk_changes(self, since: str):
        """Return latest is_risk change per vendor since `since` (YYYY-MM-DD HH:MM:SS).

        If a vendor flipped more than once in the window, only the most recent
        transition is returned so notify reports one outcome per vendor per run.
        """
        with self._connect() as conn:
            changes = pd.read_sql_query(
                f"""
                SELECT *
                FROM {CHANGES_TABLE}
                WHERE field = 'is_risk'
                  AND changed_at >= ?
                  AND NOT (
                      (old_value IS NULL OR old_value <> 1)
                      AND (new_value IS NULL OR new_value <> 1)
                  )
                ORDER BY id DESC
                """,
                conn,
                params=[since],
            )
        if changes.empty:
            return changes
        return (
            changes.sort_values("id", ascending=False)
            .drop_duplicates(subset="vendor", keep="first")
            .reset_index(drop=True)
        )

    def get_vendor_changes(self, vendor=None):
        query = f"SELECT * FROM {CHANGES_TABLE} ORDER BY id DESC"
        params = []
        if vendor is not None:
            query = (
                f"SELECT * FROM {CHANGES_TABLE} WHERE vendor = ? ORDER BY id DESC"
            )
            params = [vendor]
        with self._connect() as conn:
            return pd.read_sql_query(query, conn, params=params)

    def update_research_date(self, vendor):
        now = pd.Timestamp.now().floor("s")
        with self._connect() as conn:
            conn.execute(
                f"""
                UPDATE {TABLE}
                SET {_quote("Last Checked Date")} = ?
                WHERE {_quote("Company / Brand")} = ?
                """,
                (str(now), vendor),
            )
        self._reload()
        print(f"Updated Last Checked Date for {vendor}")

    def update_risk_fields(self, vendor, decision):
        now = pd.Timestamp.now().floor("s")
        with self._connect() as conn:
            conn.execute(
                f"""
                UPDATE {TABLE}
                SET is_risk = ?,
                    Risk_level = ?,
                    Risk_Reason = ?,
                    {_quote("Last Risk Eval")} = ?
                WHERE {_quote("Company / Brand")} = ?
                """,
                (
                    _to_sql_value(decision.is_risk),
                    _to_sql_value(decision.Risk_level),
                    decision.Risk_Reason,
                    str(now),
                    vendor,
                ),
            )
        self._reload()
        print(
            f"Updated risk fields for {vendor}: "
            f"level={decision.Risk_level}, is_risk={decision.is_risk}"
        )


if __name__ == "__main__":
    book = CompanyBook()
    vendors = book.get_vendors(3)
    print(vendors)
