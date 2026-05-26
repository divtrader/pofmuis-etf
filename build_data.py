#!/usr/bin/env python3
"""Fetch live prices from Stooq and write data.json for the web dashboard.

Run locally:   python3 build_data.py
Run in CI:     same command — no dependencies beyond stdlib
"""
import csv, json, pathlib, subprocess, datetime, io

ROOT = pathlib.Path(__file__).parent

# ── STATIC FUND DEFINITIONS ────────────────────────────────────────────────
FUNDS = {
    "apf": {
        "name": "AI Power ETF",
        "ticker": "APF",
        "inception": "2026-05-22",
        "base": 100.0,
        "spy_inc": 747.79,
        "holdings": [
            {"ticker": "VST",  "name": "Vistra Corp",          "weight": 30, "bucket": "Nuclear & Gas",    "inc": 153.165},
            {"ticker": "CEG",  "name": "Constellation Energy", "weight": 25, "bucket": "Nuclear Fleet",    "inc": 290.39},
            {"ticker": "TLN",  "name": "Talen Energy",          "weight": 20, "bucket": "Nucl. Colocation", "inc": 364.775},
            {"ticker": "NEE",  "name": "NextEra Energy",        "weight": 15, "bucket": "Renewables",       "inc": 89.18},
            {"ticker": "GEV",  "name": "GE Vernova",            "weight": 10, "bucket": "Grid Infra",       "inc": 1044.3601},
        ],
        "news": [
            {"ticker": "VST",  "headline": "Vistra Posts Record Q1 2026 EBITDA; PJM Capacity +1,038%",       "summary": "Record adjusted EBITDA driven by surging PJM capacity prices. FY2026 guidance raised, citing AI data-centre load growth.",                                                        "sentiment": "positive", "date": "2026-05-15"},
            {"ticker": "CEG",  "headline": "Constellation Signs Second Hyperscaler Nuclear PPA",               "summary": "Long-term PPA with a major hyperscaler for dedicated nuclear baseload supply, following the landmark Microsoft Three Mile Island deal.",                                       "sentiment": "positive", "date": "2026-05-10"},
            {"ticker": "TLN",  "headline": "Talen Cumulus Campus Reaches 200MW; Amazon Anchor Tenant",         "summary": "Nuclear-adjacent Cumulus data-centre campus hit 200MW operational. Management indicated >1GW pipeline at Susquehanna site.",                                                  "sentiment": "positive", "date": "2026-05-08"},
            {"ticker": "NEE",  "headline": "NextEra + Dominion Merger Approved — Southeast Grid Expansion",    "summary": "Federal regulators conditionally approved the merger, creating the nation's largest regulated utility with a 30GW renewable pipeline.",                                       "sentiment": "positive", "date": "2026-05-18"},
            {"ticker": "GEV",  "headline": "GE Vernova Transformer Backlog Hits $28B — 3-Year Delivery Wait",  "summary": "AI data-centre grid demand pushed GEV backlog to $28B with lead times extending to 3 years. Strong pricing power.",                                                          "sentiment": "positive", "date": "2026-05-20"},
        ],
        "changes": [
            "VST 30%: PEG 0.36x deeply underpriced relative to earnings growth.",
            "TLN 20%: High conviction but levered — capped to manage leverage risk.",
            "GEV 10%: Grid infrastructure pure-play but expensive (FWD P/E 55-69x, priced in).",
            "NEE 15%: Premium valuation (PEG 3.10x) limits upside vs. other positions.",
        ],
    },
    "prf": {
        "name": "Pofmuis Robotics Fund",
        "ticker": "PRF",
        "inception": "2026-05-12",
        "base": 100.0,
        "spy_inc": 739.30,
        "holdings": [
            {"ticker": "ISRG",  "name": "Intuitive Surgical",    "weight": 7.0,  "bucket": "Medical",      "inc": 420.06},
            {"ticker": "ROK",   "name": "Rockwell Automation",   "weight": 6.5,  "bucket": "Automation",   "inc": 456.66},
            {"ticker": "NVDA",  "name": "NVIDIA",                "weight": 6.0,  "bucket": "Software/AI",  "inc": 219.44},
            {"ticker": "SYM",   "name": "Symbotic",              "weight": 5.0,  "bucket": "Logistics",    "inc": 51.71},
            {"ticker": "FANUY", "name": "Fanuc (ADR)",           "weight": 5.0,  "bucket": "Industrial",   "inc": 24.17},
            {"ticker": "TER",   "name": "Teradyne",              "weight": 4.5,  "bucket": "Industrial",   "inc": 366.64},
            {"ticker": "ZBRA",  "name": "Zebra Technologies",    "weight": 4.0,  "bucket": "Automation",   "inc": 216.96},
            {"ticker": "CGNX",  "name": "Cognex",                "weight": 4.0,  "bucket": "Automation",   "inc": 67.26},
            {"ticker": "SYK",   "name": "Stryker",               "weight": 4.0,  "bucket": "Medical",      "inc": 282.58},
            {"ticker": "ABBNY", "name": "ABB Ltd (ADR)",         "weight": 3.0,  "bucket": "Industrial",   "inc": 107.73},
            {"ticker": "MDT",   "name": "Medtronic",             "weight": 3.0,  "bucket": "Medical",      "inc": 74.54},
            {"ticker": "AVAV",  "name": "AeroVironment",         "weight": 3.0,  "bucket": "Defense",      "inc": 166.45},
            {"ticker": "KTOS",  "name": "Kratos Defense",        "weight": 3.0,  "bucket": "Defense",      "inc": 56.99},
            {"ticker": "ATS",   "name": "ATS Corp",              "weight": 3.0,  "bucket": "Logistics",    "inc": 34.25},
            {"ticker": "TDY",   "name": "Teledyne Technologies", "weight": 3.0,  "bucket": "Defense",      "inc": 632.58},
            {"ticker": "PTC",   "name": "PTC Inc",               "weight": 3.0,  "bucket": "Software",     "inc": 145.92},
            {"ticker": "HON",   "name": "Honeywell",             "weight": 2.5,  "bucket": "Industrial",   "inc": 219.11},
            {"ticker": "PATH",  "name": "UiPath",                "weight": 2.5,  "bucket": "Software",     "inc": 10.66},
            {"ticker": "LMT",   "name": "Lockheed Martin",       "weight": 2.5,  "bucket": "Defense",      "inc": 512.25},
            {"ticker": "PEGA",  "name": "Pegasystems",           "weight": 2.0,  "bucket": "Software",     "inc": 34.26},
            {"ticker": "LECO",  "name": "Lincoln Electric",      "weight": 2.0,  "bucket": "Industrial",   "inc": 271.23},
            {"ticker": "OMCL",  "name": "Omnicell",              "weight": 2.0,  "bucket": "Medical",      "inc": 43.30},
            {"ticker": "AME",   "name": "Ametek",                "weight": 2.0,  "bucket": "Professional", "inc": 232.16},
            {"ticker": "OII",   "name": "Oceaneering Intl",      "weight": 2.0,  "bucket": "Professional", "inc": 37.93},
            {"ticker": "NOC",   "name": "Northrop Grumman",      "weight": 2.0,  "bucket": "Defense",      "inc": 548.21},
            {"ticker": "PRCT",  "name": "Procept BioRobotics",   "weight": 2.0,  "bucket": "Medical",      "inc": 26.45},
            {"ticker": "TSLA",  "name": "Tesla",                 "weight": 1.5,  "bucket": "Industrial",   "inc": 445.00},
            {"ticker": "AMZN",  "name": "Amazon",                "weight": 1.5,  "bucket": "Logistics",    "inc": 268.99},
            {"ticker": "ESLT",  "name": "Elbit Systems",         "weight": 1.0,  "bucket": "Defense",      "inc": 794.95},
            {"ticker": "TXT",   "name": "Textron",               "weight": 1.0,  "bucket": "Defense",      "inc": 91.66},
            {"ticker": "GD",    "name": "General Dynamics",      "weight": 1.0,  "bucket": "Defense",      "inc": 344.03},
            {"ticker": "RTX",   "name": "RTX Corporation",       "weight": 1.0,  "bucket": "Defense",      "inc": 178.61},
            {"ticker": "LHX",   "name": "L3Harris Technologies", "weight": 1.0,  "bucket": "Defense",      "inc": 302.35},
            {"ticker": "QCOM",  "name": "Qualcomm",              "weight": 1.0,  "bucket": "Software",     "inc": 237.53},
            {"ticker": "SERV",  "name": "Serve Robotics",        "weight": 1.0,  "bucket": "Logistics",    "inc": 8.85},
            {"ticker": "BA",    "name": "Boeing",                "weight": 0.5,  "bucket": "Defense",      "inc": 238.21},
            {"ticker": "PDYN",  "name": "Palladyne AI",          "weight": 0.5,  "bucket": "Software",     "inc": 6.59},
            {"ticker": "RR",    "name": "Richtech Robotics",     "weight": 0.5,  "bucket": "Service",      "inc": 2.75},
        ],
        "news": [
            {"ticker": "ABBNY", "headline": "SoftBank Acquires ABB Robotics for ~$5.3B",                            "summary": "ABB agreed to divest its Robotics division to SoftBank. Reduces pure-play exposure. ABBNY downgraded 6%→3%.",                                                        "sentiment": "mixed",    "date": "2026-03-15"},
            {"ticker": "ROK",   "headline": "Rockwell Automation Q2 FY26 Beat & Raise",                             "summary": "Q2 revenue and EPS beat consensus. Management raised FY26 guidance on reshoring demand and AI data-centre automation buildout.",                             "sentiment": "positive", "date": "2026-05-07"},
            {"ticker": "AVAV",  "headline": "AeroVironment Wins $90M LASSO Contract Extension",                     "summary": "US Army extended AVAV's LASSO loitering munition contract for $90M. Switchblade 600 gaining traction in allied military procurement.",                      "sentiment": "positive", "date": "2026-05-12"},
            {"ticker": "ISRG",  "headline": "Intuitive Q1 Beat; Minor FDA Recall on Ion Accessories",               "summary": "Intuitive beat Q1 estimates. Minor voluntary recall on certain Ion accessories; corrective action complete, no material impact.",                            "sentiment": "mixed",    "date": "2026-04-22"},
            {"ticker": "NVDA",  "headline": "NVIDIA Unveils GR00T N1 Humanoid Foundation Model",                    "summary": "NVIDIA launched GR00T N1 at GTC — a general-purpose humanoid foundation model trained on human motion data. Direct Isaac platform uplift.",                 "sentiment": "positive", "date": "2026-03-18"},
            {"ticker": "SYM",   "headline": "Symbotic Expands Walmart Deal — 42 RDCs, $5B+ Backlog",               "summary": "Symbotic secured expanded deployment across all 42 Walmart regional distribution centres. Backlog uplift exceeds $5B.",                                     "sentiment": "positive", "date": "2026-04-10"},
            {"ticker": "TER",   "headline": "Teradyne Opens Michigan Cobot Hub with NVIDIA AI",                     "summary": "New Universal Robots AI training hub in Michigan. Cognitive Cobot platform powered by NVIDIA runs natural-language task programming.",                       "sentiment": "positive", "date": "2026-05-05"},
            {"ticker": "TSLA",  "headline": "Optimus Production Delayed to Q4 2026",                                "summary": "Tesla pushed Optimus mass production targets to Q4 2026, citing actuator supply constraints. Beta units still on track for internal factory deployment.", "sentiment": "negative", "date": "2026-05-01"},
        ],
        "changes": [
            "ABBNY (ABB ADR) added — source used 'ABB' but only ABBNY trades as ADR. Downgraded 6%→3% after SoftBank robotics acquisition.",
            "FANUY (Fanuc ADR) added — not in source list; only mega-cap pure-play left after ABB divestiture.",
            "FARO Technologies → AME (Ametek) — FARO delisted Jul 2025 after $920M Ametek acquisition.",
            "IRBT (iRobot) removed — filed Chapter 11 Jan 2026, delisted.",
        ],
    },
    "pmf": {
        "name": "Pofmuis Memory Fund",
        "ticker": "PMF",
        "inception": "2026-05-26",
        "base": 100.0,
        "spy_inc": 751.41,
        "holdings": [
            {"ticker": "MU",   "name": "Micron Technology",            "weight": 35, "bucket": "HBM/DRAM",             "inc": 881.76},
            {"ticker": "SNDK", "name": "SanDisk",                      "weight": 20, "bucket": "NAND Flash",           "inc": 1596.46},
            {"ticker": "WDC",  "name": "Western Digital",              "weight": 15, "bucket": "Storage Systems",      "inc": 532.275},
            {"ticker": "STX",  "name": "Seagate Technology",           "weight": 10, "bucket": "Mass Storage",         "inc": 845.00},
            {"ticker": "RMBS", "name": "Rambus",                       "weight": 10, "bucket": "Memory IP",            "inc": 158.23},
            {"ticker": "NTAP", "name": "NetApp",                       "weight": 5,  "bucket": "Hybrid Cloud Storage", "inc": 137.98},
            {"ticker": "DELL", "name": "Dell Technologies",            "weight": 3,  "bucket": "Enterprise Solutions", "inc": 303.34},
            {"ticker": "HPE",  "name": "Hewlett Packard Enterprise",   "weight": 2,  "bucket": "Enterprise Storage",   "inc": 37.95},
        ],
        "news": [
            {"ticker": "MU",   "headline": "Micron HBM4 Production Ramps — Sold Out Through 2027",   "summary": "Micron confirmed HBM4 production ramping at Boise. Capacity sold out through 2027 with hyperscaler reservation contracts. Mix shift expected to drive gross margin to 50%+.", "sentiment": "positive", "date": "2026-05-22"},
            {"ticker": "SNDK", "headline": "SanDisk QLC Wins Meta Datacenter SSD Contract",          "summary": "SanDisk QLC enterprise SSDs selected for Meta's next-gen AI training clusters. ASP uplift and multi-year volume commitment.",                                            "sentiment": "positive", "date": "2026-05-18"},
            {"ticker": "WDC",  "headline": "WD HAMR Drives Hit 40TB — Hyperscaler Qualification Complete", "summary": "Western Digital's 40TB HAMR drives passed final qualification at two major hyperscalers. Mass production ramps Q3 2026.",                                          "sentiment": "positive", "date": "2026-05-15"},
            {"ticker": "STX",  "headline": "Seagate Mozaic 3+ Generation Launches — 50TB Roadmap",   "summary": "Seagate announced Mozaic 3+ HAMR platform with 50TB roadmap. AI dataset storage demand pulling forward HDD ASPs.",                                                   "sentiment": "positive", "date": "2026-05-20"},
            {"ticker": "RMBS", "headline": "Rambus DDR5 Royalties Up 41% YoY",                       "summary": "Rambus reported DDR5 royalty revenue up 41% YoY. Memory interface IP attached to every server DRAM shipment.",                                                         "sentiment": "positive", "date": "2026-05-12"},
            {"ticker": "NTAP", "headline": "NetApp Q4 In-line; FY27 Guide Below Street",             "summary": "NetApp Q4 met expectations but FY27 guide came in slightly below consensus. Cloud transition optics cited.",                                                            "sentiment": "mixed",    "date": "2026-05-08"},
            {"ticker": "DELL", "headline": "Dell PowerStore AI Hits $2B ARR",                        "summary": "Dell PowerStore AI storage line crossed $2B annual run-rate. Hyperscaler-adjacent enterprise winning AI infrastructure refresh.",                                    "sentiment": "positive", "date": "2026-05-21"},
            {"ticker": "HPE",  "headline": "HPE Alletra Storage Wins UK Government Cloud",           "summary": "HPE Alletra MP storage selected for UK G-Cloud framework. Sovereign AI compute demand driving enterprise storage growth.",                                           "sentiment": "positive", "date": "2026-05-14"},
        ],
        "changes": [
            "MU 35%: Pure-play HBM leader — biggest AI memory cycle beneficiary",
            "SNDK 20%: Post-spinoff pure-play NAND leader, hyperscaler SSD wins",
            "RMBS 10%: Royalty IP model — every DDR5/HBM stack pays Rambus",
            "DELL/HPE 5% combined: Enterprise storage refresh cycle exposure, not pure memory",
        ],
    },
}

# ── FETCH PRICES VIA STOOQ ──────────────────────────────────────────────────
def fetch_stooq(tickers: list[str]) -> dict:
    """Fetch Stooq EOD CSV one ticker at a time.
    Stooq returns bare data rows with no header:
      SYMBOL.US,DATE,TIME,OPEN,HIGH,LOW,CLOSE,VOLUME
    """
    import time
    HEADER = "Symbol,Date,Time,Open,High,Low,Close,Volume\n"
    prices = {}
    for i, t in enumerate(tickers):
        if i > 0 and i % 10 == 0:
            time.sleep(1)  # brief pause every 10 requests
        try:
            result = subprocess.run(
                ["curl", "-s", "-A", "Mozilla/5.0",
                 f"https://stooq.com/q/l/?s={t.lower()}.us&f=sd2t2ohlcv&e=csv"],
                capture_output=True, text=True, timeout=12
            )
            raw = result.stdout.strip()
            if not raw or "N/D" in raw.split(",")[4:]:
                continue
            reader = csv.DictReader(io.StringIO(HEADER + raw))
            for row in reader:
                sym = row["Symbol"].replace(".US", "")
                close_val = row.get("Close", "")
                open_val  = row.get("Open", "")
                if close_val not in ("N/D", "", None):
                    prices[sym] = {
                        "close": float(close_val),
                        "open":  float(open_val) if open_val not in ("N/D", "") else float(close_val),
                        "date":  row["Date"],
                    }
        except Exception as e:
            print(f"  Warning: {t} — {e}")
    return prices

# ── COMPUTE ONE FUND ────────────────────────────────────────────────────────
def compute_fund(fd: dict, prices: dict) -> dict:
    rows, nav_change, day_change = [], 0.0, 0.0
    for h in fd["holdings"]:
        t   = h["ticker"]
        inc = h["inc"]
        cur = prices.get(t, {}).get("close")
        opn = prices.get(t, {}).get("open") or cur
        ret = (cur / inc - 1) * 100 if cur and inc else 0.0
        day = (cur / opn - 1) * 100 if cur and opn else 0.0
        contrib = ret * h["weight"] / 100
        nav_change += contrib
        day_change += day * h["weight"] / 100
        rows.append({
            **h,
            "cur":     cur,
            "ret":     round(ret, 4),
            "day":     round(day, 4),
            "contrib": round(contrib, 4),
            "date":    prices.get(t, {}).get("date", ""),
        })
    nav = fd["base"] * (1 + nav_change / 100)
    spy_cur = prices.get("SPY", {}).get("close")
    spy_ret = round((spy_cur / fd["spy_inc"] - 1) * 100, 4) if spy_cur else None
    alpha   = round(nav_change - spy_ret, 4) if spy_ret is not None else None
    return {
        "nav":       round(nav, 4),
        "nav_change": round(nav_change, 4),
        "day_change": round(day_change, 4),
        "spy_ret":   spy_ret,
        "alpha":     alpha,
        "rows":      rows,
        "news":      fd["news"],
        "changes":   fd["changes"],
    }

# ── MAIN ────────────────────────────────────────────────────────────────────
def main():
    # Collect all unique tickers
    all_tickers = list({
        h["ticker"]
        for fd in FUNDS.values()
        for h in fd["holdings"]
    } | {"SPY"})

    print(f"Fetching {len(all_tickers)} tickers from Stooq…")
    prices = fetch_stooq(all_tickers)
    print(f"  Got prices for: {sorted(prices.keys())}")

    as_of = next(iter(prices.values()))["date"] if prices else "—"
    now   = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    out = {
        "generated":  now,
        "as_of":      as_of,
        "spy_price":  prices.get("SPY", {}).get("close"),
        "apf": compute_fund(FUNDS["apf"], prices),
        "prf": compute_fund(FUNDS["prf"], prices),
        "pmf": compute_fund(FUNDS["pmf"], prices),
    }

    path = ROOT / "data.json"
    path.write_text(json.dumps(out, indent=2))
    print(f"Wrote {path}  —  APF NAV {out['apf']['nav']:.4f} ({out['apf']['nav_change']:+.2f}%)  PRF NAV {out['prf']['nav']:.4f} ({out['prf']['nav_change']:+.2f}%)  PMF NAV {out['pmf']['nav']:.4f} ({out['pmf']['nav_change']:+.2f}%)")
    update_history(out, ROOT)


def update_history(out, root):
    """Append hourly NAV snapshot to history.json for charting."""
    path = root / "history.json"
    try:
        entries = json.loads(path.read_text()) if path.exists() else []
    except Exception:
        entries = []

    point = {
        "ts": out["generated"],
        "apf": out["apf"]["nav_change"],
        "prf": out["prf"]["nav_change"],
        "pmf": out["pmf"]["nav_change"],
        "spy_apf": out["apf"]["spy_ret"],
        "spy_prf": out["prf"]["spy_ret"],
        "spy_pmf": out["pmf"]["spy_ret"],
    }

    # Update existing entry if same hour, else append
    ts_hour = point["ts"][:13]
    if entries and entries[-1]["ts"][:13] == ts_hour:
        entries[-1] = point
    else:
        entries.append(point)

    entries = entries[-1000:]  # cap at 1000 entries
    path.write_text(json.dumps(entries))
    print(f"Updated {path}  ({len(entries)} entries)")


if __name__ == "__main__":
    main()
