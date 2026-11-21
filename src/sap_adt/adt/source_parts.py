"""Named class source parts; locking and activation always use the parent."""
PARTS = ("main", "definitions", "implementations", "testclasses")


def source_path(object_uri: str, part: str = "main") -> str:
    if part not in PARTS:
        raise ValueError(f"unsupported source part: {part}")
    if part != "main" and not object_uri.startswith("/sap/bc/adt/oo/classes/"):
        raise ValueError("named source parts are supported only for classes")
    return object_uri + ("/source/main" if part == "main" else f"/includes/{part}")
