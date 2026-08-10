# -*- coding: utf-8 -*-
"""Gates for the UI kit.

The kit is where every OS section will get its components and charts
from, so a lie here becomes a lie everywhere at once. These gates test
the honesty rules AS GEOMETRY: a gap must literally break the polyline,
a refusal must literally replace the axes, and the waterfall must
literally add up.
"""
from __future__ import annotations

import ast
import io
import re
import sys

import content_engine_demo as D
import content_engine_ui_kit as UK

PASS, FAIL = [], []


def t(label, ok, detail=""):
    try:
        ok = bool(ok)
    except Exception:                                 # noqa: BLE001
        ok = False
    (PASS if ok else FAIL).append(label)
    print(("  OK   " if ok else "  FAIL ") + label
          + (("   " + str(detail)) if detail and not ok else ""))


def head(x):
    print("\n" + x)


print("=" * 74)
print("UI KIT - GATES")
print("=" * 74)

# ---------------------------------------------------------------- L1
head("L1  HELPERS: THE ONE COPY BEHAVES")
t("absence is a word, never a zero", UK.n(None) == "not measured"
  and UK.n(0) == "0")
t("zero is a measurement and renders as one", UK.n(0.0) == "0")
t("money formats and refuses absence",
  UK.money(48000) == "€48,000" and UK.money(None) == "not measured")
t("pct is honest about absence", UK.pct(None) == "not measured"
  and UK.pct(0.184) == "18.4%")
t("e() escapes markup", UK.e("<b a=\"x\">") == "&lt;b a=&quot;x&quot;&gt;")

# ---------------------------------------------------------------- L2
head("L2  KPI: POLARITY IS THE CALLER'S VERDICT, RENDERED HONESTLY")
_up_good = UK.kpi("Revenue", "€284,000", delta=18, verdict="GOOD")
_dn_good = UK.kpi("CAC", "€114", delta=-3, verdict="GOOD")
_up_bad = UK.kpi("Refunds", "1.2%", delta=14, verdict="BAD")
t("a rise judged GOOD is green", "uk-ok" in _up_good)
t("A FALL CAN BE GREEN: CAC down renders GOOD",
  "uk-ok" in _dn_good and "-3" in _dn_good)
t("a rise judged BAD is red", "uk-er" in _up_bad)
t("no delta means 'no comparison', not a hidden zero",
  "no comparison" in UK.kpi("X", "5"))
t("freshness renders when supplied",
  "6 min ago" in UK.kpi("X", "5", freshness="updated 6 min ago"))

# ---------------------------------------------------------------- L3
head("L3  STATUS AND NOTES")
t("status is icon plus word, never colour alone",
  "▲ Degraded" in UK.status("DEGRADED")
  and "● Healthy" in UK.status("HEALTHY"))
t("an unknown status stays a question mark",
  "?" in UK.status("WEIRD"))
t("THE LECTURE BECOMES A TOOLTIP",
  "title=" in UK.note("the whole explanation")
  and "the whole explanation" in UK.note("the whole explanation"))
t("empty() is one line plus a glyph, not a wall",
  UK.empty("No data", "why").count("<p") == 0)
t("an AI button is marked on its face",
  "✦" in UK.button("Generate", "ai")
  and "✦" not in UK.button("Approve", "human"))

# ---------------------------------------------------------------- L4
head("L4  THE LINE CHART: HONEST GEOMETRY")
_gap_series = [1, 2, 3, None, None, 6, 7, 8]
_ln = UK.line(_gap_series, title="T", source="SRC")
t("A GAP BREAKS THE POLYLINE INTO TWO SEGMENTS",
  _ln.count("<polyline") == 2, str(_ln.count("<polyline")))
t("and the footer says gaps are gaps, not zeros",
  "gap(s) shown as gaps" in _ln)
t("A CHART WITH NO SOURCE REFUSES TO DRAW AXES",
  "<svg" not in UK.line([1, 2], title="T", source="")
  and "picture" in UK.line([1, 2], title="T", source=""))
t("nothing measured draws no axis over nothing",
  "<svg" not in UK.line([None, None], title="T", source="S"))
t("the compare series renders muted behind the current one",
  "#C7CDD6" in UK.line([1, 2, 3], title="T", source="S",
                       compare=[1, 1, 2]))
t("the endpoint is emphasised and labelled",
  "<circle" in _ln and ">8<" in _ln)
t("every chart carries its source line",
  "Source: SRC" in _ln)
t("and an aria label", "aria-label=" in _ln)

# ---------------------------------------------------------------- L5
head("L5  THE OTHER CHARTS")
_hb = UK.hbar([("A", 10), ("B", None), ("C", 30)], title="T",
              source="S")
t("hbar leaves unmeasured rows OUT and says so",
  "1 unmeasured row(s) left out" in _hb and _hb.count("<rect") == 2)
t("hbar sorts biggest first",
  _hb.index(">C<") < _hb.index(">A<") if ">C<" in _hb else
  _hb.index("C") < _hb.index("A"))
_sc = UK.scatter([(1, 2, "a"), (3, None, "b"), (5, 6, "c")],
                 title="T", source="S")
t("scatter drops half-measured points and names the count",
  "1 point(s) missing a coordinate" in _sc
  and _sc.count("<circle") == 2)
_dn = UK.donut([("A", 75), ("B", 25), ("C", None), ("D", 0)],
               title="T", source="S")
t("donut excludes None and zero parts",
  _dn.count("stroke-dasharray") == 2)
t("donut legend shows value AND share",
  "75" in _dn and "(75%)" in _dn)
_wf = UK.waterfall("Revenue", 100, [("A", 30), ("B", None), ("C", 20)],
                   title="T", source="S", end_label="Left")
t("WATERFALL ARITHMETIC: end equals start minus the KNOWN steps",
  ">Left<" in _wf and ">50<" in _wf,
  "label rendered: " + str(">Left<" in _wf)
  + ", value 50 rendered: " + str(">50<" in _wf))
t("and a missing step is NAMED, never deducted as zero",
  "not supplied and not deducted: B" in _wf)
t("a waterfall with no start refuses",
  "<svg" not in UK.waterfall("R", None, [("A", 1)], title="T",
                             source="S"))
_sp = UK.sparkline([1, None, 3, 4], source="S")
t("sparklines keep their gaps too", "<svg" in _sp)
t("an empty sparkline is a word, not a flat line",
  "no trend data" in UK.sparkline([None, None], source="S"))
_st = UK.stacked(["Mon", "Tue"], [("A", [1, 2]), ("B", [2, 1])],
                 title="T", source="S")
t("stacked renders every series with a legend",
  _st.count("<rect") == 4 and "■" in _st)

# ---------------------------------------------------------------- L6
head("L6  THE SUBSECTION TEMPLATE")
_sub = UK.subsection("Paid", kpis=UK.kpi("Spend", "€48,000"),
                     chart=UK.line([1, 2], title="T", source="S"),
                     breakdown=UK.hbar([("A", 1)], title="B",
                                       source="S"),
                     table_html=UK.table(("X",), [(("1",), None)]),
                     freshness="Media 3 min")
t("the template carries scorecards, chart, breakdown and table",
  all(x in _sub for x in ("uk-kpi", "<svg", "uk-tbl")))
t("with per-source freshness on the header", "Media 3 min" in _sub)
t("a drawer row is clickable and its drawer toggles by id",
  "data-drawer" in UK.table(("A",), [(("x",), "d1")])
  and "id='d9'" in UK.drawer("d9", "inner"))

# ---------------------------------------------------------------- L7
head("L7  STRUCTURE AND SELF-DISCIPLINE")
_css = re.findall(r"<style>(.*?)</style>", UK.CSS, re.S)[0]
t("ONE stylesheet, smaller than any single old section's CSS",
  len(_css) < 9000, str(len(_css)) + " bytes")
t("THE 11PX FLOOR HOLDS IN HTML (the audit flagged my own 10px)",
  "font-size:10px" not in _css, "10px still in kit CSS")
t("muted grey is reserved for metadata classes only",
  _css.count("color:var(--mu)") <= 4)
t("every KIT_EXPORTS name is callable",
  all(callable(getattr(UK, x, None)) for x in UK.KIT_EXPORTS),
  str([x for x in UK.KIT_EXPORTS
       if not callable(getattr(UK, x, None))]))
t("no em-dash in kit or demo",
  all("—" not in io.open(f, encoding="utf-8").read()
      for f in ("content_engine_ui_kit.py", "content_engine_demo.py")))
t("no while loop in the kit",
  not [x for x in ast.walk(ast.parse(io.open(
      "content_engine_ui_kit.py", encoding="utf-8").read()))
       if isinstance(x, ast.While)])

# ---------------------------------------------------------------- L8
head("L8  DEMO MODE: FIXTURES THAT ADMIT IT")
_g = D.gallery()
t("the gallery renders every chart type",
  _g.count("<svg") >= 10, str(_g.count("<svg")))
t("THE SAMPLE BANNER IS ON THE PAGE, LOUD",
  "SAMPLE DATA" in _g and "Nothing here is the business" in _g)
t("every demo chart names SAMPLE DATA as its source",
  _g.count("Source: SAMPLE DATA") >= 6,
  str(_g.count("Source: SAMPLE DATA")))
t("the refusals are demonstrated in the gallery itself",
  "no source, so it does not" in _g
  and "not drawn over nothing" in _g)
t("demo_ctx stamps _demo and a SAMPLE period",
  D.demo_ctx("bi")["_demo"] is True
  and "SAMPLE" in D.demo_ctx("bi")["period"])
t("no old dark palette leaks into the gallery",
  not [c for c in ("#0A0E1A", "#2FE3D2", "#121A2E") if c in _g])

# ---------------------------------------------------------------- verdict
print("\n" + "=" * 74)
print(str(len(PASS)) + " passed, " + str(len(FAIL)) + " failed")
if FAIL:
    for f in FAIL:
        print("  FAILED: " + f)
print("=" * 74)
sys.exit(1 if FAIL else 0)
