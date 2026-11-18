import csv
import io
import json
import xml.etree.ElementTree as ET
from xml.dom import minidom

from fpdf import FPDF

from app.present import lookup_out


def _safe(text) -> str:
    if text is None:
        return ""
    return str(text).encode("latin-1", "replace").decode("latin-1")


def as_json(rows: list) -> bytes:
    payload = [lookup_out(r) for r in rows]
    return json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")


def as_csv(rows: list) -> bytes:
    buf = io.StringIO()
    fields = [
        "id",
        "query",
        "location",
        "country",
        "latitude",
        "longitude",
        "date",
        "tmin",
        "tmax",
        "tmean",
        "precip",
        "condition",
        "notes",
    ]
    w = csv.DictWriter(buf, fieldnames=fields)
    w.writeheader()
    for row in rows:
        body = lookup_out(row)
        loc = body["location"]["name"]
        days = body.get("days") or [{}]
        for d in days:
            w.writerow(
                {
                    "id": body["id"],
                    "query": body["query"],
                    "location": loc,
                    "country": body["location"]["country"],
                    "latitude": body["location"]["latitude"],
                    "longitude": body["location"]["longitude"],
                    "date": d.get("date", ""),
                    "tmin": d.get("tmin", ""),
                    "tmax": d.get("tmax", ""),
                    "tmean": d.get("tmean", ""),
                    "precip": d.get("precip", ""),
                    "condition": d.get("condition", ""),
                    "notes": body.get("notes", ""),
                }
            )
    return buf.getvalue().encode("utf-8")


def _el(parent, tag, text=None):
    node = ET.SubElement(parent, tag)
    if text is not None:
        node.text = "" if text is None else str(text)
    return node


def as_xml(rows: list) -> bytes:
    root = ET.Element("lookups")
    for row in rows:
        body = lookup_out(row)
        node = ET.SubElement(root, "lookup", id=str(body["id"]))
        _el(node, "query", body["query"])
        loc = _el(node, "location")
        for k, v in body["location"].items():
            _el(loc, k, v)
        _el(node, "start_date", body["start_date"])
        _el(node, "end_date", body["end_date"])
        _el(node, "notes", body["notes"])
        days = _el(node, "days")
        for d in body.get("days") or []:
            day = ET.SubElement(days, "day")
            for k, v in d.items():
                _el(day, k, v)
    rough = ET.tostring(root, encoding="utf-8")
    pretty = minidom.parseString(rough).toprettyxml(indent="  ", encoding="utf-8")
    return pretty


def as_md(rows: list) -> bytes:
    parts = ["# Waypoint weather export", ""]
    for body in (lookup_out(r) for r in rows):
        loc = body["location"]
        parts.append(f"## {loc['name']} (`{body['id']}`)")
        parts.append(f"- Query: {body['query']}")
        parts.append(f"- Range: {body['start_date']} → {body['end_date']}")
        s = body["summary"]
        u = body["unit_labels"]["temp"]
        parts.append(f"- Avg {s['avg']}°{u} (min {s['min']} / max {s['max']}), rain days {s['rain_days']}")
        if body.get("notes"):
            parts.append(f"- Notes: {body['notes']}")
        maps = (body.get("extras") or {}).get("maps") or {}
        if maps.get("google_maps"):
            parts.append(f"- Map: {maps['google_maps']}")
        yt = (body.get("extras") or {}).get("youtube") or {}
        if yt.get("search_url"):
            parts.append(f"- YouTube: {yt['search_url']}")
        parts.append("")
        parts.append("| Date | Min | Max | Mean | Precip | Sky |")
        parts.append("| --- | --- | --- | --- | --- | --- |")
        for d in body.get("days") or []:
            parts.append(
                f"| {d['date']} | {d['tmin']} | {d['tmax']} | {d['tmean']} | {d['precip']} | {d['condition']} |"
            )
        parts.append("")
    return "\n".join(parts).encode("utf-8")


def as_pdf(rows: list) -> bytes:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=16)
    usable = 180
    for row in rows:
        body = lookup_out(row)
        loc = body["location"]
        pdf.add_page()
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "B", 14)
        pdf.multi_cell(usable, 8, _safe("Waypoint Wx export"))
        pdf.set_font("Helvetica", "B", 16)
        pdf.multi_cell(usable, 8, _safe(loc["name"]))
        pdf.set_font("Helvetica", size=10)
        s = body["summary"]
        u = body["unit_labels"]["temp"]
        lines = [
            f"{body['start_date']} to {body['end_date']} | query: {body['query']}",
            f"avg {s['avg']} {u}  min {s['min']}  max {s['max']}  rain days {s['rain_days']}",
        ]
        if body.get("notes"):
            lines.append("notes: " + body["notes"])
        maps = (body.get("extras") or {}).get("maps") or {}
        if maps.get("google_maps"):
            lines.append("map: " + maps["google_maps"])
        for line in lines:
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(usable, 6, _safe(line))
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 9)
        cols = [("Date", 34), ("Min", 22), ("Max", 22), ("Mean", 24), ("Precip", 26), ("Sky", 52)]
        pdf.set_x(pdf.l_margin)
        for h, w in cols:
            pdf.cell(w, 7, h, border=1)
        pdf.ln()
        pdf.set_font("Helvetica", size=8)
        for d in body.get("days") or []:
            vals = [
                _safe(d["date"]),
                str(d["tmin"]),
                str(d["tmax"]),
                str(d["tmean"]),
                str(d["precip"]),
                _safe(d["condition"]),
            ]
            pdf.set_x(pdf.l_margin)
            for text, (_, w) in zip(vals, cols):
                pdf.cell(w, 6, text[:28], border=1)
            pdf.ln()
    return bytes(pdf.output())


EXPORTERS = {
    "json": ("application/json", ".json", as_json),
    "csv": ("text/csv", ".csv", as_csv),
    "xml": ("application/xml", ".xml", as_xml),
    "md": ("text/markdown", ".md", as_md),
    "markdown": ("text/markdown", ".md", as_md),
    "pdf": ("application/pdf", ".pdf", as_pdf),
}
