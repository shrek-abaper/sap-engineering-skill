"""kind=capabilities: the ADT discovery Atom service document.

GET /sap/bc/adt/discovery returns an ``app:service`` document with one
``app:collection`` per exposed resource: ``href``, ``atom:title`` and zero
or more ``app:accept`` media types. Resources that do not declare an
acceptable content type (usageReferences, datapreview, checkruns, …) yield
an empty ``content_types`` list.
"""
from __future__ import annotations

APP = "http://www.w3.org/2007/app"
ATOM = "http://www.w3.org/2005/Atom"
COMPATIBILITY = "http://www.sap.com/adt/compatibility"


def parse(payload: bytes) -> dict:
    import xml.etree.ElementTree as ET

    root = ET.fromstring(payload)
    collections = []
    for col in root.iter(f"{{{APP}}}collection"):
        title = col.find(f"{{{ATOM}}}title")
        collection = {
            "href": col.get("href"),
            "title": title.text if title is not None else None,
            "content_types": [a.text for a in col.findall(f"{{{APP}}}accept") if a.text],
        }
        templates = [{
            "href": link.get("template"),
            "content_types": [link.get("type")] if link.get("type") else [],
        } for link in col.iter(f"{{{COMPATIBILITY}}}templateLink") if link.get("template")]
        if templates:
            collection["templates"] = templates
        collections.append(collection)
    # Stable order (discovery already is, but do not rely on it).
    collections.sort(key=lambda c: c["href"] or "")
    return {"collections": collections}
