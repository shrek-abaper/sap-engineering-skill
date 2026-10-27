"""kind=rows: data-preview freestyle SQL results (column-oriented XML)."""
from __future__ import annotations

from .common import ParseError, attr, localname, parse_xml


def parse(payload: bytes) -> dict:
    root = parse_xml(payload)
    if localname(root.tag) != "tableData":
        raise ParseError(f"not a dataPreview tableData document (root <{root.tag}>)")

    columns: list[dict] = []
    column_values: list[list[str | None]] = []
    for col in root:
        if localname(col.tag) != "columns":
            continue
        metadata = None
        data_set = None
        for child in col:
            if localname(child.tag) == "metadata":
                metadata = child
            elif localname(child.tag) == "dataSet":
                data_set = child
        if metadata is None:
            continue
        columns.append({
            "name": attr(metadata, "name"),
            "type": attr(metadata, "type"),
        })
        values = []
        if data_set is not None:
            for cell in data_set:
                if localname(cell.tag) != "data":
                    continue
                values.append(cell.text)
        column_values.append(values)

    row_count = min((len(v) for v in column_values), default=0)
    rows = [[column_values[c][r] for c in range(len(columns))]
            for r in range(row_count)]
    return {"columns": columns, "rows": rows}
