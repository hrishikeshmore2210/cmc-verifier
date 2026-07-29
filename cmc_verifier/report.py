"""HTML discrepancy report renderer (ARCHITECTURE.md §4).

Turns adjudicated flags into a self-contained, shareable HTML report — grouped by
severity, each flag showing the dossier section, the reported-vs-source detail,
the provenance pointer, and the check that raised it. No external assets; the CSS
is inline so the file opens anywhere.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone

_SEVERITY_ORDER = ["critical", "major", "minor"]
_SEVERITY_COLOR = {"critical": "#b3261e", "major": "#b8860b", "minor": "#3a6ea5"}

_CSS = """<style>
  body { font-family: -apple-system, "Segoe UI", Roboto, sans-serif; margin:0; background:#f4f5f7; color:#1a1a1a; }
  header { background:#0f1b2d; color:#fff; padding:20px 28px; }
  header h1 { margin:0; font-size:18px; letter-spacing:.3px; }
  header .sub { opacity:.7; font-size:12px; margin-top:4px; }
  .wrap { max-width:900px; margin:0 auto; padding:24px 28px; }
  .summary { display:flex; gap:10px; align-items:center; margin-bottom:20px; }
  .summary .total { font-size:26px; font-weight:700; margin-right:8px; }
  .chip { border:1px solid; border-radius:12px; padding:2px 10px; font-size:12px; text-transform:capitalize; }
  h2 { font-size:14px; text-transform:uppercase; letter-spacing:.5px; margin:22px 0 10px; }
  .flag { background:#fff; border-left:4px solid #555; border-radius:6px; padding:12px 14px; margin-bottom:10px;
          box-shadow:0 1px 2px rgba(0,0,0,.06); }
  .flag-head { display:flex; gap:10px; align-items:center; margin-bottom:6px; }
  .sev { color:#fff; font-size:10px; font-weight:700; padding:2px 8px; border-radius:10px; }
  .check { font-family:ui-monospace, Menlo, monospace; font-size:12px; color:#333; }
  .conf { margin-left:auto; font-size:11px; color:#888; }
  .msg { font-size:14px; margin:2px 0 6px; }
  .meta { display:flex; gap:18px; font-size:12px; color:#555; margin-bottom:4px; }
  .rationale { font-size:12px; color:#777; font-style:italic; }
  .clean { color:#2e7d32; font-weight:600; }
  footer { max-width:900px; margin:0 auto; padding:0 28px 30px; font-size:11px; color:#999; }
</style>"""


def _esc(x):
    return html.escape("" if x is None else str(x))


def _sev_value(sev):
    return sev.value if hasattr(sev, "value") else str(sev)


def _source_ref_str(ref):
    if ref is None:
        return "—"
    parts = [ref.document_id]
    if ref.page is not None:
        parts.append(f"p.{ref.page}")
    if ref.location:
        parts.append(ref.location)
    return ", ".join(parts)


def _flag_card(flag):
    sev = _sev_value(flag.severity)
    color = _SEVERITY_COLOR.get(sev, "#555")
    return (
        f'<div class="flag" style="border-left-color:{color}">'
        f'<div class="flag-head">'
        f'<span class="sev" style="background:{color}">{_esc(sev.upper())}</span>'
        f'<span class="check">{_esc(flag.check_name)}</span>'
        f'<span class="conf">confidence {flag.confidence:.2f}</span>'
        f'</div>'
        f'<div class="msg">{_esc(flag.message)}</div>'
        f'<div class="meta">'
        f'<span>Section: {_esc(flag.dossier_ref or "—")}</span>'
        f'<span>Source: {_esc(_source_ref_str(flag.source_ref))}</span>'
        f'</div>'
        f'<div class="rationale">{_esc(flag.rationale)}</div>'
        f'</div>'
    )


def render_html_report(report, flags, title="CMC Verification — Discrepancy Report"):
    by_sev = report.get("by_severity", {})
    total = report.get("total_flags", len(flags))
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    grouped = {s: [f for f in flags if _sev_value(f.severity) == s] for s in _SEVERITY_ORDER}
    sections = []
    for sev in _SEVERITY_ORDER:
        fs = grouped[sev]
        if not fs:
            continue
        cards = "".join(_flag_card(f) for f in fs)
        sections.append(f'<h2 style="color:{_SEVERITY_COLOR[sev]}">{sev.upper()} ({len(fs)})</h2>{cards}')
    body = "".join(sections) or '<p class="clean">No discrepancies found.</p>'

    summary_chips = "".join(
        f'<span class="chip" style="border-color:{_SEVERITY_COLOR[s]};color:{_SEVERITY_COLOR[s]}">'
        f'{s}: {by_sev.get(s, 0)}</span>'
        for s in _SEVERITY_ORDER
    )

    return (
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">\n'
        f"<title>{_esc(title)}</title>\n"
        f"{_CSS}\n"
        "</head><body>\n"
        f'<header><h1>{_esc(title)}</h1>'
        f'<div class="sub">Generated {generated} · verify-first · human adjudication required</div></header>\n'
        f'<div class="wrap"><div class="summary"><span class="total">{total}</span>{summary_chips}</div>\n'
        f"{body}</div>\n"
        '<footer>Every flag is a candidate discrepancy for a qualified reviewer to adjudicate. '
        "This report does not resolve findings.</footer>\n"
        "</body></html>"
    )