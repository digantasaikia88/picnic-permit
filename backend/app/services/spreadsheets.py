"""Reading uploaded CSV or Excel lists, and writing Excel downloads."""

import csv
import io

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from app.core.errors import DomainError

MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_ROWS = 5000
XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _clean(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def read_table(filename: str, content: bytes) -> list[dict[str, str]]:
    """Read the first sheet of an .xlsx file, or a .csv file, as a list of rows.

    The first row holds the column names. Blank rows are skipped.
    """
    if len(content) > MAX_UPLOAD_BYTES:
        raise DomainError("The file is larger than 2 MB.")

    name = filename.lower()
    if name.endswith(".xlsx"):
        try:
            workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        except Exception as exc:
            raise DomainError("The Excel file could not be read.") from exc
        raw_rows = [
            [_clean(cell) for cell in row] for row in workbook.active.iter_rows(values_only=True)
        ]
    elif name.endswith(".csv"):
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise DomainError("The CSV file must be saved as UTF-8.") from exc
        raw_rows = [[_clean(cell) for cell in row] for row in csv.reader(io.StringIO(text))]
    else:
        raise DomainError("Upload an Excel (.xlsx) or CSV (.csv) file.")

    raw_rows = [row for row in raw_rows if any(row)]
    if not raw_rows:
        raise DomainError("The file is empty.")

    headers = raw_rows[0]
    rows = [
        {header: (row[i] if i < len(row) else "") for i, header in enumerate(headers) if header}
        for row in raw_rows[1:]
    ]
    if not rows:
        raise DomainError("The file has a heading row but no data rows.")
    if len(rows) > MAX_ROWS:
        raise DomainError(f"The file has more than {MAX_ROWS} rows.")
    return rows


def require_columns(rows: list[dict[str, str]], columns: list[str]) -> None:
    missing = [column for column in columns if column not in rows[0]]
    if missing:
        raise DomainError("The file is missing these columns: " + ", ".join(missing) + ".")


def write_xlsx(headers: list[str], rows: list[list[object]], *, sheet_title: str) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = sheet_title
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for row in rows:
        sheet.append(row)
    sheet.freeze_panes = "A2"
    for index, header in enumerate(headers, start=1):
        longest = max([len(str(header))] + [len(str(row[index - 1] or "")) for row in rows])
        sheet.column_dimensions[get_column_letter(index)].width = min(longest + 2, 60)

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
