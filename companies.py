from contextlib import contextmanager
from pathlib import Path
import sqlite3

import pandas as pd

DEFAULT_DB_PATH = Path(__file__).resolve().with_name("suppliers.db")
DEFAULT_EXCEL_PATH = Path(__file__).resolve().with_name("real_pro_av_companies.xlsx")
TABLE = "vendors"


def _quote(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


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
