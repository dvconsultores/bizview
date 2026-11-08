"""Google Sheets origin (feature 061).

One worksheet is one table; the first row is the header; types are inferred from the first N rows at
describe time and **declared** in the integration, which is what every run enforces (research R4).
A sheet has no SQL, so an integration over it carries a request-like extraction: the kind is `api`
in the registry, and `values.get` is the only call it makes.
"""
import json
import re
from datetime import date, datetime

from app.config import Settings
from app.i18n import t
from app.sources.connectors import sql as sqlbase
from app.sources.connectors.base import TestResult, fail

kind = "sheets"
label = "sources.kind.sheets"
SCOPES = ("https://www.googleapis.com/auth/spreadsheets.readonly",
          "https://www.googleapis.com/auth/drive.metadata.readonly")
RANGE_ROWS = 10_000
SHEET_ID = re.compile(r"/spreadsheets/d/([A-Za-z0-9_-]{20,})")
TYPES = ("string", "integer", "number", "date", "datetime", "bool")


def _sdk():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    return service_account, build


def service_account_info(secrets: dict) -> dict:
    raw = (secrets or {}).get("service_account") or ""
    try:
        info = json.loads(raw) if isinstance(raw, str) else dict(raw)
    except ValueError:
        raise ValueError("sources.sheets.bad_json") from None
    if not info.get("client_email") or not info.get("private_key"):
        raise ValueError("sources.sheets.missing_keys")
    return info


def credentials(secrets: dict):
    info = service_account_info(secrets)
    service_account, _ = _sdk()
    return service_account.Credentials.from_service_account_info(info, scopes=SCOPES), info


def service_account_email(secrets: dict) -> str | None:
    """The address the sheet has to be shared with, read without the SDK."""
    try:
        return service_account_info(secrets).get("client_email")
    except ValueError:
        return None


def spreadsheet_id(url: str) -> str:
    """The id inside a Sheets URL (or the id itself)."""
    value = str(url or "").strip()
    match = SHEET_ID.search(value)
    if match:
        return match.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{20,}", value):
        return value
    raise ValueError("sources.sheets.bad_url")


def client(secrets: dict):
    creds, _info = credentials(secrets)
    _, build = _sdk()
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def classify(error: BaseException) -> str:
    text = str(error).lower()
    if "403" in text and ("permission" in text or "forbidden" in text or "not been used" in text):
        return "auth_failed"
    if "404" in text:
        return "not_found"
    if "quota" in text or "rate limit" in text or "429" in text or "too many" in text:
        return "busy"
    if "timeout" in text or "timed out" in text:
        return "timeout"
    if "401" in text or "invalid_grant" in text or "pem file" in text:
        return "auth_failed"
    return "unreachable"


def is_busy(error: BaseException) -> bool:
    return classify(error) == "busy"


def _worksheets(service, sheet_id: str) -> list[dict]:
    meta = service.spreadsheets().get(spreadsheetId=sheet_id, includeGridData=False).execute()
    return [{"title": sheet.get("properties", {}).get("title", ""),
             "rows": sheet.get("properties", {}).get("gridProperties", {}).get("rowCount", 0),
             "columns": sheet.get("properties", {}).get("gridProperties", {}).get("columnCount", 0)}
            for sheet in meta.get("sheets", [])]


def test(settings: dict, secrets: dict, app: Settings) -> TestResult:
    try:
        info = service_account_info(secrets)
    except ValueError as e:          # the JSON itself: a key a person can act on
        return TestResult(False, "auth_failed", message=t(e.args[0]))
    try:
        sheet_id = spreadsheet_id(settings.get("url", ""))
    except ValueError as e:
        return TestResult(False, "not_found", message=t(e.args[0]))
    try:
        service = client(secrets)
        sheets = _worksheets(service, sheet_id)
    except Exception as e:
        code = classify(e)
        message = fail(code, sqlbase.safe(e, secrets), secrets).message
        if code == "auth_failed":
            email = info.get("client_email", "")
            return TestResult(False, code,
                              message=f"{message} ({t('sources.sheets.share_with')}: {email})")
        return TestResult(False, code, message=message)
    return TestResult(True, details={"service_account": info.get("client_email", ""),
                                     "worksheets": len(sheets)})


def _infer(values: list[str]) -> str:
    """The narrowest type every sample fits; ISO dates before numbers, booleans before text."""
    def fits(kind_name: str) -> bool:
        for value in values:
            text = str(value).strip()
            if not text:
                continue
            try:
                if kind_name == "integer" and not re.fullmatch(r"[-+]?\d+", text):
                    return False
                if kind_name == "number":
                    float(text.replace(".", "", text.count(".") - 1).replace(",", "."))
                if kind_name == "date":
                    date.fromisoformat(text)
                if kind_name == "datetime":
                    datetime.fromisoformat(text.replace("Z", "+00:00"))
                if kind_name == "bool" and text.lower() not in ("true", "false", "si", "sí", "no",
                                                                "0", "1"):
                    return False
            except ValueError:
                return False
        return True

    for candidate in ("integer", "number", "date", "datetime", "bool"):
        if fits(candidate):
            return candidate
    return "string"


def describe(settings: dict, secrets: dict, app: Settings, *, path: str | None = None,
             write_probe: bool = False, date_ranges: bool = False,
             name: str | None = None) -> dict:
    """Each worksheet as a table: header row, inferred types, row count. Never the values."""
    sheet_id = spreadsheet_id(settings.get("url", ""))
    header_row = int(settings.get("header_row") or 1)
    sample = int(settings.get("sample_rows") or 200)
    service = client(secrets)
    tables = []
    for sheet in _worksheets(service, sheet_id):
        title = sheet["title"]
        rows = service.spreadsheets().values().get(
            spreadsheetId=sheet_id, range=f"'{title}'!A{header_row}:ZZ{header_row + sample}"
        ).execute().get("values", [])
        if not rows:
            tables.append({"schema": "sheets", "name": title, "kind": "table", "columns": [],
                           "rows": 0})
            continue
        header, *samples = rows
        columns = []
        for index, label in enumerate(header):
            column_samples = [row[index] for row in samples if index < len(row)]
            columns.append({"name": str(label or f"col{index + 1}").strip(),
                            "type": _infer(column_samples), "nullable": True})
        tables.append({"schema": "sheets", "name": title, "kind": "table", "columns": columns,
                       "rows": max(0, sheet.get("rows", 0) - header_row)})
    return {"kind": kind, "tables": tables, "truncated": False, "dialect": dialect_notes()}


def dialect_notes() -> dict:
    return {"kind": "sheets", "quote": "", "limit": "", "identifier_case": "sensitive",
            "notes": "No SQL: one worksheet is one table; the first row is the header; declare "
                     "the column types in the integration (they come from the structure pack)."}


def read(sheet_id: str, secrets: dict, worksheet: str, *, start_row: int = 1,
         batch: int = RANGE_ROWS) -> list[list[str]]:
    """The rows of a worksheet in chunks of at most `RANGE_ROWS`: never the whole sheet at once."""
    service = client(secrets)
    out: list[list[str]] = []
    row = start_row
    while True:
        chunk = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"'{worksheet}'!A{row}:ZZ{row + batch - 1}").execute().get("values", [])
        out.extend(chunk)
        if len(chunk) < batch:
            return out
        row += batch


def request_rows(settings: dict, secrets: dict, app: Settings, request: dict, params: dict,
                 columns: list[str], *, time_limit_s: int, cancel=None):
    """One worksheet as rows of dicts: the header row names the columns.

    A sheet has no SQL, so its integration declares the request (`worksheet`, optional
    `header_row`); each value arrives as the text the cell holds and the staging table parses it
    for the declared type, so a cell that does not match becomes a null or a contract error —
    never a crash (spec US4).
    """
    request = request or {}
    sheet_id = spreadsheet_id(settings.get("url", ""))
    worksheet = request.get("worksheet")
    if not worksheet:
        raise ValueError(t("sources.sheets.worksheet_required"))
    header_row = int(request.get("header_row") or settings.get("header_row") or 1)
    from app.engine.extract import Cancelled

    rows = read(sheet_id, secrets, worksheet, start_row=header_row)
    if not rows:
        return
    header, *body = rows
    index: dict[str, int] = {}
    for position, label in enumerate(header):
        index.setdefault(str(label or "").strip(), position)
    positions = []
    for position, column in enumerate(columns):
        found = index.get(column)
        positions.append(found if found is not None else position)
    for batch in _batches(body):
        if cancel is not None and cancel.cancelled:
            raise Cancelled()
        yield [{column: _cell(row, position)
                for column, position in zip(columns, positions, strict=True)} for row in batch]


BATCH_ROWS = 5_000


def _batches(rows: list[list[str]]):
    for start in range(0, len(rows), BATCH_ROWS):
        yield rows[start:start + BATCH_ROWS]


def _cell(row: list, position: int) -> str | None:
    value = row[position] if position < len(row) else None
    text = "" if value is None else str(value).strip()
    return text or None
