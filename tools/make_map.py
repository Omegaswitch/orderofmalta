#!/usr/bin/env python3 -I
"""Build the data of the interactive world map (stdlib only, run with: python3 -I tools/make_map.py [world-atlas countries-50m.json]).

Writes
  static/map/world.svg              one <path id=ISO3 data-iso=ISO3> per country (Equal Earth, no Antarctica) plus <circle> markers
                                    for countries too small to click at map scale
  static/map/presence.<lang>.json   {ISO3: {"entities": [{name, kind, web?, email?}], "anchor": region id on the contacts page}}

Geometry: Natural Earth (public domain) through the npm package world-atlas 2.0.2 (countries-50m.json, ISC licence).
Download it outside the repository, e.g.
  curl -L https://registry.npmjs.org/world-atlas/-/world-atlas-2.0.2.tgz | tar xz -C /some/empty/dir   (file: package/countries-50m.json)
Presence: parsed from the imported Contacts pages in content/pages/<lang>/<contacts>/index.html. Nothing is written that is not on those pages.
"""
import difflib
import html
import json
import math
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "static" / "map"
LANGS = ["en", "it", "fr", "de", "es"]
CONTACT_DIR = {"en": "contacts", "it": "contatti", "fr": "contacts", "de": "kontakte", "es": "contactos"}

W = 1000.0          # map width in SVG units
DEC = 1             # decimals kept in path coordinates
TOL = 0.12          # Douglas-Peucker tolerance (SVG units), applied per arc so shared borders stay shared
MIN_RING = 0.6      # rings with a bounding-box diagonal below this are dropped
SMALL = 9.0         # a present country narrower than this (units) gets a marker circle
PAD = 4.0

# numeric ISO 3166-1 -> (ISO3, ISO2)
NUM = {k: tuple(v.split()) for k, v in {
    "004": "AFG AF", "008": "ALB AL", "012": "DZA DZ", "016": "ASM AS", "020": "AND AD", "024": "AGO AO", "028": "ATG AG", "031": "AZE AZ",
    "032": "ARG AR", "036": "AUS AU", "040": "AUT AT", "044": "BHS BS", "048": "BHR BH", "050": "BGD BD", "051": "ARM AM", "052": "BRB BB",
    "056": "BEL BE", "060": "BMU BM", "064": "BTN BT", "068": "BOL BO", "070": "BIH BA", "072": "BWA BW", "076": "BRA BR", "084": "BLZ BZ",
    "086": "IOT IO", "090": "SLB SB", "092": "VGB VG", "096": "BRN BN", "100": "BGR BG", "104": "MMR MM", "108": "BDI BI", "112": "BLR BY",
    "116": "KHM KH", "120": "CMR CM", "124": "CAN CA", "132": "CPV CV", "136": "CYM KY", "140": "CAF CF", "144": "LKA LK", "148": "TCD TD",
    "152": "CHL CL", "156": "CHN CN", "158": "TWN TW", "170": "COL CO", "174": "COM KM", "178": "COG CG", "180": "COD CD", "184": "COK CK",
    "188": "CRI CR", "191": "HRV HR", "192": "CUB CU", "196": "CYP CY", "203": "CZE CZ", "204": "BEN BJ", "208": "DNK DK", "212": "DMA DM",
    "214": "DOM DO", "218": "ECU EC", "222": "SLV SV", "226": "GNQ GQ", "231": "ETH ET", "232": "ERI ER", "233": "EST EE", "234": "FRO FO",
    "238": "FLK FK", "239": "SGS GS", "242": "FJI FJ", "246": "FIN FI", "248": "ALA AX", "250": "FRA FR", "258": "PYF PF", "260": "ATF TF",
    "262": "DJI DJ", "266": "GAB GA", "268": "GEO GE", "270": "GMB GM", "275": "PSE PS", "276": "DEU DE", "288": "GHA GH", "296": "KIR KI",
    "300": "GRC GR", "304": "GRL GL", "308": "GRD GD", "316": "GUM GU", "320": "GTM GT", "324": "GIN GN", "328": "GUY GY", "332": "HTI HT",
    "334": "HMD HM", "336": "VAT VA", "340": "HND HN", "344": "HKG HK", "348": "HUN HU", "352": "ISL IS", "356": "IND IN", "360": "IDN ID",
    "364": "IRN IR", "368": "IRQ IQ", "372": "IRL IE", "376": "ISR IL", "380": "ITA IT", "384": "CIV CI", "388": "JAM JM", "392": "JPN JP",
    "398": "KAZ KZ", "400": "JOR JO", "404": "KEN KE", "408": "PRK KP", "410": "KOR KR", "414": "KWT KW", "417": "KGZ KG", "418": "LAO LA",
    "422": "LBN LB", "426": "LSO LS", "428": "LVA LV", "430": "LBR LR", "434": "LBY LY", "438": "LIE LI", "440": "LTU LT", "442": "LUX LU",
    "446": "MAC MO", "450": "MDG MG", "454": "MWI MW", "458": "MYS MY", "462": "MDV MV", "466": "MLI ML", "470": "MLT MT", "478": "MRT MR",
    "480": "MUS MU", "484": "MEX MX", "492": "MCO MC", "496": "MNG MN", "498": "MDA MD", "499": "MNE ME", "500": "MSR MS", "504": "MAR MA",
    "508": "MOZ MZ", "512": "OMN OM", "516": "NAM NA", "520": "NRU NR", "524": "NPL NP", "528": "NLD NL", "531": "CUW CW", "533": "ABW AW",
    "534": "SXM SX", "540": "NCL NC", "548": "VUT VU", "554": "NZL NZ", "558": "NIC NI", "562": "NER NE", "566": "NGA NG", "570": "NIU NU",
    "574": "NFK NF", "578": "NOR NO", "580": "MNP MP", "583": "FSM FM", "584": "MHL MH", "585": "PLW PW", "586": "PAK PK", "591": "PAN PA",
    "598": "PNG PG", "600": "PRY PY", "604": "PER PE", "608": "PHL PH", "612": "PCN PN", "616": "POL PL", "620": "PRT PT", "624": "GNB GW",
    "626": "TLS TL", "630": "PRI PR", "634": "QAT QA", "642": "ROU RO", "643": "RUS RU", "646": "RWA RW", "652": "BLM BL", "654": "SHN SH",
    "659": "KNA KN", "660": "AIA AI", "662": "LCA LC", "663": "MAF MF", "666": "SPM PM", "670": "VCT VC", "674": "SMR SM", "678": "STP ST",
    "682": "SAU SA", "686": "SEN SN", "688": "SRB RS", "690": "SYC SC", "694": "SLE SL", "702": "SGP SG", "703": "SVK SK", "704": "VNM VN",
    "705": "SVN SI", "706": "SOM SO", "710": "ZAF ZA", "716": "ZWE ZW", "724": "ESP ES", "728": "SSD SS", "729": "SDN SD", "732": "ESH EH",
    "740": "SUR SR", "748": "SWZ SZ", "752": "SWE SE", "756": "CHE CH", "760": "SYR SY", "762": "TJK TJ", "764": "THA TH", "768": "TGO TG",
    "776": "TON TO", "780": "TTO TT", "784": "ARE AE", "788": "TUN TN", "792": "TUR TR", "795": "TKM TM", "796": "TCA TC", "800": "UGA UG",
    "804": "UKR UA", "807": "MKD MK", "818": "EGY EG", "826": "GBR GB", "831": "GGY GG", "832": "JEY JE", "833": "IMN IM", "834": "TZA TZ",
    "840": "USA US", "850": "VIR VI", "854": "BFA BF", "858": "URY UY", "860": "UZB UZ", "862": "VEN VE", "876": "WLF WF", "882": "WSM WS",
    "887": "YEM YE", "894": "ZMB ZM"}.items()}
# features without a numeric id in the data
BY_NAME = {"Kosovo": "XKX", "Somaliland": "SOM", "N. Cyprus": "CYP", "Indian Ocean Ter.": "AUS", "Ashmore and Cartier Is.": "AUS"}
DROP = {"010", "Siachen Glacier"}   # Antarctica, a glacier without a country

# lon/lat of the capital (or main island) for countries too small to click on the map
MARKERS = {
    "MLT": (14.51, 35.90), "VAT": (12.45, 41.90), "SMR": (12.45, 43.94), "MCO": (7.42, 43.74), "AND": (1.52, 42.51), "LIE": (9.52, 47.14),
    "LUX": (6.13, 49.61), "ATG": (-61.85, 17.12), "GRD": (-61.68, 12.12), "LCA": (-60.98, 13.91), "VCT": (-61.20, 13.25),
    "BRB": (-59.55, 13.10), "BHS": (-77.35, 25.05), "SYC": (55.45, -4.62), "MUS": (57.50, -20.25), "CPV": (-23.60, 15.10),
    "COM": (43.25, -11.70), "STP": (6.73, 0.34), "KIR": (173.0, 1.45), "MHL": (171.2, 7.10), "FSM": (158.2, 6.92), "NRU": (166.93, -0.53),
    "SGP": (103.82, 1.35), "HKG": (114.17, 22.32), "PRI": (-66.45, 18.22), "PSE": (35.20, 31.90), "LBN": (35.85, 33.85),
}

# EN country headings (as written in the Contacts page) -> ISO3
HEAD = {
    "ALBANIA": "ALB", "ANDORRA": "AND", "AUSTRIA": "AUT", "BELARUS": "BLR", "BELGIUM": "BEL", "BOSNIA-HERZEGOVINA": "BIH", "BULGARIA": "BGR",
    "CYPRUS": "CYP", "CROATIA": "HRV", "CZECHIA": "CZE", "ESTONIA": "EST", "FRANCE": "FRA", "GERMANY": "DEU", "GREECE": "GRC", "HOLY SEE": "VAT",
    "HUNGARY": "HUN", "IRELAND": "IRL", "ITALY": "ITA", "LATVIA": "LVA", "LIECHTENSTEIN": "LIE", "LITHUANIA": "LTU", "LUXEMBOURG": "LUX",
    "MALTA": "MLT", "MOLDOVA": "MDA", "MONACO": "MCO", "MONTENEGRO": "MNE", "NETHERLANDS": "NLD", "NORTH MACEDONIA": "MKD", "POLAND": "POL",
    "PORTUGAL": "PRT", "ROMANIA": "ROU", "RUSSIAN FEDERATION": "RUS", "SAN MARINO": "SMR", "SERBIA": "SRB", "SLOVAKIA": "SVK", "SLOVENIA": "SVN",
    "SPAIN": "ESP", "SWEDEN": "SWE", "SWITZERLAND": "CHE", "UNITED KINGDOM": "GBR", "UKRAINE": "UKR",
    "ANGOLA": "AGO", "BENIN": "BEN", "BURKINA FASO": "BFA", "BURUNDI": "BDI", "CAMEROON": "CMR", "CAPE VERDE": "CPV", "CENTRAL AFRICA": "CAF",
    "CHAD": "TCD", "COMOROS": "COM", "DEMOCRATIC REPUBLIC OF THE CONGO": "COD", "REPUBLIC OF THE CONGO": "COG", "CÔTE D’IVOIRE": "CIV",
    "EGYPT": "EGY", "EQUATORIAL GUINEA": "GNQ", "ERITREA": "ERI", "ETHIOPIA": "ETH", "GABON": "GAB", "GAMBIA, THE": "GMB", "GUINEA": "GIN",
    "GUINEA BISSAU": "GNB", "KENYA": "KEN", "LESOTHO": "LSO", "LIBERIA": "LBR", "MADAGASCAR": "MDG", "MALI": "MLI", "MAURITANIA": "MRT",
    "MAURITIUS": "MUS", "MOROCCO": "MAR", "MOZAMBIQUE": "MOZ", "NAMIBIA": "NAM", "NIGER": "NER", "NIGERIA": "NGA", "SAO TOME AND PRINCIPE": "STP",
    "SENEGAL": "SEN", "SEYCHELLES": "SYC", "SIERRA LEONE": "SLE", "SOUTH AFRICA": "ZAF", "SOUTH SUDAN": "SSD", "SUDAN": "SDN", "TOGO": "TGO",
    "ANTIGUA AND BARBUDA": "ATG", "ARGENTINA": "ARG", "THE BAHAMAS": "BHS", "BELIZE": "BLZ", "BOLIVIA": "BOL", "BRAZIL": "BRA", "CANADA": "CAN",
    "CHILE": "CHL", "COLOMBIA": "COL", "COSTA RICA": "CRI", "CUBA": "CUB", "DOMINICAN REPUBLIC": "DOM", "ECUADOR": "ECU", "EL SALVADOR": "SLV",
    "GRENADA": "GRD", "GUATEMALA": "GTM", "GUYANA": "GUY", "HAITI": "HTI", "HONDURAS": "HND", "MEXICO": "MEX", "NICARAGUA": "NIC", "PANAMA": "PAN",
    "PARAGUAY": "PRY", "PERU": "PER", "PUERTO RICO": "PRI", "SAINT LUCIA": "LCA", "SAINT VINCENT AND THE GRENADINES": "VCT", "SURINAME": "SUR",
    "UNITED STATES OF AMERICA": "USA", "URUGUAY": "URY", "VENEZUELA": "VEN",
    "AFGHANISTAN": "AFG", "ARMENIA": "ARM", "CAMBODIA": "KHM", "GEORGIA": "GEO", "HONG KONG": "HKG", "JORDAN": "JOR", "LEBANON": "LBN",
    "KAZAKHSTAN": "KAZ", "PALESTINE": "PSE", "PHILIPPINES": "PHL", "SINGAPORE": "SGP", "SOUTH KOREA": "KOR", "TAJIKISTAN": "TJK", "THAILAND": "THA",
    "TIMOR LESTE": "TLS", "TURKMENISTAN": "TKM", "AUSTRALIA": "AUS", "KIRIBATI": "KIR", "MARSHALL ISLANDS": "MHL", "MICRONESIA": "FSM",
    "NAOERO": "NRU",  # the page's spelling of Nauru
    "NEW ZEALAND": "NZL",
}
# the four international seats listed first on every Contacts page, in page order -> the country of their address
SEATS = ["ITA", "DEU", "USA", "CHE"]

# ---------------------------------------------------------------- geometry


def equal_earth(lon, lat):
    a1, a2, a3, a4 = 1.340264, -0.081106, 0.000893, 0.003796
    th = math.asin(math.sqrt(3) / 2 * math.sin(math.radians(lat)))
    t2, t6 = th * th, th ** 6
    x = 2 * math.sqrt(3) * math.radians(lon) * math.cos(th) / (3 * (9 * a4 * t2 ** 4 + 7 * a3 * t6 + 3 * a2 * t2 + a1))
    y = th * (a4 * t2 ** 4 + a3 * t6 + a2 * t2 + a1)
    return x, -y


def decode_arcs(topo):
    sx, sy = topo["transform"]["scale"]
    tx, ty = topo["transform"]["translate"]
    out = []
    for arc in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arc:
            x += dx
            y += dy
            pts.append(equal_earth(x * sx + tx, y * sy + ty))
        out.append(pts)
    return out


def dp(pts, tol):
    """Douglas-Peucker (iterative) keeping both end points."""
    if len(pts) < 3:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        (ax, ay), (bx, by) = pts[a], pts[b]
        dx, dy = bx - ax, by - ay
        L = math.hypot(dx, dy)
        best, idx = -1.0, a
        for i in range(a + 1, b):
            px, py = pts[i]
            d = abs(dy * (px - ax) - dx * (py - ay)) / L if L else math.hypot(px - ax, py - ay)
            if d > best:
                best, idx = d, i
        if best > tol:
            keep[idx] = True
            stack += [(a, idx), (idx, b)]
    return [p for p, k in zip(pts, keep) if k]


def ring_points(arcs, ring):
    pts = []
    for i in ring:
        a = arcs[i] if i >= 0 else arcs[~i][::-1]
        pts += a if not pts else a[1:]
    return pts


def fmt(n):
    s = f"{n:.{DEC}f}".rstrip("0").rstrip(".")
    if s in ("", "-0"):
        s = "0"
    return s.replace("0.", ".", 1) if s.startswith("0.") else s.replace("-0.", "-.", 1)


def ring_path(pts):
    q = [(round(x * 10 ** DEC), round(y * 10 ** DEC)) for x, y in pts]
    dedup = [q[0]]
    for p in q[1:]:
        if p != dedup[-1]:
            dedup.append(p)
    if len(dedup) > 1 and dedup[0] == dedup[-1]:
        dedup.pop()
    if len(dedup) < 3:
        return ""
    k = 10 ** DEC
    d = "M" + fmt(dedup[0][0] / k) + " " + fmt(dedup[0][1] / k) + "l"
    prev, last = dedup[0], ""
    for p in dedup[1:]:
        for v in (fmt((p[0] - prev[0]) / k), fmt((p[1] - prev[1]) / k)):
            d += v if (v.startswith("-") or not last) else " " + v
            last = v
        prev = p
    return d + "z"


def build_geometry(topo, present):
    tol = TOL / ((W - 2 * PAD) / (2 * equal_earth(180, 0)[0]))   # tolerance in projection units
    arcs = [dp(a, tol) for a in decode_arcs(topo)]
    feats = {}   # iso3 -> list of rings (point lists)
    for g in topo["objects"]["countries"]["geometries"]:
        gid, name = g.get("id"), g["properties"]["name"]
        if gid in DROP or name in DROP:
            continue
        iso = NUM[gid][0] if gid in NUM else BY_NAME.get(name)
        if not iso:
            raise SystemExit(f"unmapped feature {gid} {name}")
        polys = g["arcs"] if g["type"] == "MultiPolygon" else [g["arcs"]] if g["type"] == "Polygon" else []
        for poly in polys:
            for ring in poly:
                feats.setdefault(iso, []).append(ring_points(arcs, ring))
    xs = [p[0] for rs in feats.values() for r in rs for p in r]
    ys = [p[1] for rs in feats.values() for r in rs for p in r]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    s = (W - 2 * PAD) / (x1 - x0)
    ox, oy = PAD - x0 * s, PAD - y0 * s
    H = (y1 - y0) * s + 2 * PAD
    tf = lambda p: (p[0] * s + ox, p[1] * s + oy)
    paths, boxes = [], {}
    for iso in sorted(feats):
        d = ""
        xs2, ys2 = [], []
        for r in feats[iso]:
            pr = [tf(p) for p in r]
            px, py = [p[0] for p in pr], [p[1] for p in pr]
            if math.hypot(max(px) - min(px), max(py) - min(py)) < MIN_RING:
                continue
            d += ring_path(pr)
            xs2 += px
            ys2 += py
        if d:
            paths.append(f'<path id="{iso}" data-iso="{iso}" d="{d}"/>')
            boxes[iso] = (min(xs2), min(ys2), max(xs2), max(ys2))
        else:
            boxes[iso] = None
    # markers: explicit capital position, or the middle of the box for other small present countries
    circles = []
    for iso in sorted(present):
        if iso in MARKERS:
            cx, cy = tf(equal_earth(*MARKERS[iso]))
        else:
            b = boxes.get(iso)
            if b is None:
                print("WARNING: present country without geometry or marker:", iso)
                continue
            if max(b[2] - b[0], b[3] - b[1]) >= SMALL:
                continue
            cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        circles.append(f'<circle id="m-{iso}" data-iso="{iso}" cx="{fmt(cx)}" cy="{fmt(cy)}" r="3"/>')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {fmt(W)} {fmt(H)}">\n<g id="countries">\n' + "\n".join(paths) +
           '\n</g>\n<g id="markers">\n' + "\n".join(circles) + "\n</g>\n</svg>\n")
    return svg, sorted(feats), len(circles)

# ---------------------------------------------------------------- contacts

# Classification keywords, matched against the accent-folded lower-case name (see fold_text). Default kind: "works".
DIPLO = re.compile(r"mission|mision|bevollm|delegac|delegaz|delegat|embass|ambassad|ambasciat|botschaft|embajad|represent|rappresent|vertretung|diplomat")
WORKS = re.compile(r"\b(corps|corpo|cuerpo|korps|ambulan\w*|relief|volunteer\w*|voluntar\w*|freiwillig\w*|benevole\w*|aid|soccors\w*|secours|hilf\w*|"
                   r"foundation|fondation|fondazione|fundacion|fundacao|stiftung|service|servizio|servicio|dienst\w*|hospital\w*|hospitalier\w*)\b")
ORDER = re.compile(r"priory|prieure|priorat\w*|priorato|association|associazione|assoziation|asociacion|companions|compagnons|compagni|gefahrten|"
                   r"companeros|order of malta in |ordine di malta in |ordre de malte (?:en|au|a) |malteserorden in |orden de malta en |"
                   r"government|gouvernement|governo|regierung|gobierno")
SMALL_WORDS = {"of", "the", "to", "in", "and", "de", "del", "della", "dello", "dei", "delle", "di", "da", "du", "des", "la", "le", "les", "el", "los", "las",
               "et", "e", "y", "en", "au", "aux", "für", "und", "von", "zu", "zum", "zur", "der", "die", "das", "dem", "den", "al", "a", "pour", "par", "sur", "il", "lo", "gli", "ante", "presso", "a", "ai", "alla", "nella", "nel", "con", "per", "fur", "bei"}
ACRONYMS = {"CIOMAL", "CISOM", "ACISMOM", "FHOME", "IPU", "UIP", "USA", "UK", "EU", "UN", "FAO", "WFP", "IFAD", "PAM", "ONU", "UNESCO", "UNIDO",
            "ESCAP", "CESAP", "ONUDI", "OMV", "MHD", "MHDA"}
ELISION = {"l", "d", "dell", "all", "nell", "sull", "un", "c", "qu", "s", "n", "j", "m", "t"}


def fold_text(s):
    return unicodedata.normalize("NFD", s.lower()).encode("ascii", "ignore").decode()


def title_case(s):
    """Names that the page sets in capitals are shown in title case; mixed-case names are left as written. Acronyms in brackets or standing
    alone after a dash (… – CISOM) keep their capitals."""
    letters = [c for c in s if c.isalpha()]
    if not letters or sum(c.isupper() for c in letters) / len(letters) < 0.8:
        return s
    keep = set(re.findall(r"\(([^()]+)\)", s)) | ACRONYMS
    out = []
    pos = 0
    for part in re.split(r"(\([^()]+\))", s):
        if part.startswith("(") and part.endswith(")") and part[1:-1] in keep:
            out.append(part)
            pos += 1
            continue
        for w in re.split(r"(\s+)", part):
            if not w.strip():
                out.append(w)
                continue
            m = re.match(r"^(\W*)(.*?)(\W*)$", w, re.S)
            pre, core, post = m.groups()
            if core in keep:
                out.append(w)
            else:
                out.append(pre + case_word(core, pos) + post)
            pos += 1
    return "".join(out)


def case_word(core, pos):
    low = core.lower()
    m = re.match(r"^(\w+)([’'])(\w.*)$", low)
    if m and m.group(1) in ELISION:
        return m.group(1) + m.group(2) + case_word(m.group(3), 1)
    if low in SMALL_WORDS and pos:
        return low
    return "-".join(p[:1].upper() + p[1:] for p in low.split("-"))


def classify(name):
    n = fold_text(name)
    if DIPLO.search(n):
        return "diplomatic"
    if WORKS.search(n):
        return "works"
    if ORDER.search(n):
        return "order"
    return "works"


def clean(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def parse_contacts(lang):
    f = ROOT / "content" / "pages" / lang / CONTACT_DIR[lang] / "index.html"
    body = f.read_text(encoding="utf-8").split("\n---\n", 1)[1]
    countries = []   # (heading, region id, [entity dict])
    for rid, sec in re.findall(r'<section class="region" id="([^"]+)">(.*?)</section>', body, re.S):
        for summ, inner in re.findall(r"<summary>(.*?)</summary>\s*<div class=\"acc-body\">(.*?)</div>\s*</details>", sec, re.S):
            ents = []
            for p in re.findall(r"<p>(.*?)</p>", inner, re.S):
                if not re.search(r"[^\W_]", clean(p)):
                    continue   # placeholder line
                first = re.split(r"<br\s*/?>", re.sub(r"</strong>\s*<strong>", "", p), maxsplit=1)[0]
                text = clean(first).rstrip(":").strip()
                lead = re.match(r"\s*<strong>", p)
                is_name = bool(text) and "@" not in text and not re.match(r"(?i)(e-?mail|tel|web|chancer|fax)", text) and (
                    (lead and not re.match(r"\s*<strong>\s*<a ", p)) or (sum(c.isupper() for c in text if c.isalpha()) / max(1, sum(c.isalpha() for c in text)) > .85 and len(text) > 8))
                if is_name or not ents:
                    ents.append({"name": text, "html": p})
                else:
                    ents[-1]["html"] += " <br> " + p   # continuation paragraph of the same entry
            countries.append((clean(summ), rid, ents))
    return countries


def finish_entity(e):
    web = email = None
    for href in re.findall(r'href="\s*([^"]*?)\s*"', e["html"]):
        if href.lower().startswith("mailto:"):
            email = email or html.unescape(href[7:]).strip()
        elif re.match(r"https?://", href, re.I) or href.startswith("/"):
            web = web or html.unescape(href)
    name = title_case(e["name"])
    out = {"name": name, "kind": classify(e["name"])}
    if web:
        out["web"] = web
    if email:
        out["email"] = email
    return out


def signature(ents):
    sig = set()
    for e in ents:
        for href in re.findall(r'href="\s*([^"]*?)\s*"', e["html"]):
            h = html.unescape(href).lower()
            if h.startswith("mailto:"):
                sig.add(h[7:].strip())
            elif re.match(r"https?://", h):
                sig.add(re.sub(r"^https?://(www\.)?", "", h).split("/")[0])
    return sig


def fold(s):
    return re.sub(r"[^a-z]", "", unicodedata.normalize("NFD", s.lower()).encode("ascii", "ignore").decode())


def match_countries(cs, en_countries):
    """Country headings are sorted alphabetically in each language, so the order of appearance differs from EN. Match every country of a
    language to the EN country of the same continent with the most e-mail addresses and web hosts in common (the addresses are the same in
    all languages); the heading's spelling only breaks ties and decides what is left over. Returns (list of EN indexes, log lines)."""
    regs = {}
    for _, rid, _ in en_countries:
        regs.setdefault(rid, len(regs))
    lregs = {}
    for _, rid, _ in cs:
        lregs.setdefault(rid, len(lregs))
    en_sig = [signature(c[2]) for c in en_countries]
    cand = []
    for i, (h, rid, ents) in enumerate(cs):
        if i == 0:
            continue
        sg = signature(ents)
        for j, (eh, erid, _) in enumerate(en_countries):
            if j == 0 or regs[erid] != lregs[rid]:
                continue
            ratio = difflib.SequenceMatcher(None, fold(h), fold(eh)).ratio()
            cand.append((len(sg & en_sig[j]) + ratio / 2, len(sg & en_sig[j]), ratio, i, j))
    cand.sort(reverse=True)
    res, used, log = {0: 0}, {0}, []
    for score, n, ratio, i, j in cand:
        if i in res or j in used:
            continue
        res[i] = j
        used.add(j)
        if n == 0:
            log.append(f"matched by name only: {cs[i][0]} = {en_countries[j][0]} ({ratio:.2f})")
    if len(res) != len(cs):
        raise SystemExit("could not match all countries")
    return [res[i] for i in range(len(cs))], log


def build_presence(lang, en_countries):
    cs = parse_contacts(lang)
    log = []
    en_iso = [None if i == 0 else HEAD.get(h.upper()) for i, (h, _, _) in enumerate(en_countries)]
    if None in en_iso[1:]:
        raise SystemExit("unmapped EN heading: " + str([h for (h, _, _), v in zip(en_countries[1:], en_iso[1:]) if v is None]))
    if lang == "en":
        use, idx = en_countries, list(range(len(en_countries)))
    elif len(cs) != len(en_countries):
        log.append(f"count differs ({len(cs)} vs EN {len(en_countries)}): using EN entries")
        use, idx = en_countries, list(range(len(en_countries)))
    else:
        use = cs
        idx, mlog = match_countries(cs, en_countries)
        log += mlog
    pres = {}
    for i, (head, rid, ents) in enumerate(use):
        if i == 0:   # international seats
            pairs = list(zip(SEATS, ents))
            if len(ents) != len(SEATS):
                log.append(f"seats block has {len(ents)} entries, expected {len(SEATS)}")
        else:
            pairs = [(en_iso[idx[i]], e) for e in ents]
        for iso, e in pairs:
            pres.setdefault(iso, {"entities": [], "anchor": rid})["entities"].append(finish_entity(e))
    for i, (head, rid, ents) in enumerate(use):   # a country's anchor is the region of its own heading, not of the seats block
        if i and en_iso[idx[i]] in pres:
            pres[en_iso[idx[i]]]["anchor"] = rid
    if use is cs:
        for i, (h, r, ents) in enumerate(cs):
            if i and len(ents) != len(en_countries[idx[i]][2]):
                log.append(f"entity count differs for {h} = {en_countries[idx[i]][0]}: {len(ents)} vs {len(en_countries[idx[i]][2])}")
        log.append("pairs: " + "; ".join(f"{cs[i][0]}={en_countries[idx[i]][0]}" for i in range(1, len(cs))))
    return {k: v for k, v in pres.items() if v["entities"]}, log


def main():
    topo_path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if not topo_path or not topo_path.exists():
        raise SystemExit("usage: python3 -I tools/make_map.py path/to/countries-50m.json")
    topo = json.loads(topo_path.read_text(encoding="utf-8"))
    en_countries = parse_contacts("en")
    OUT.mkdir(parents=True, exist_ok=True)
    allp = {}
    for lang in LANGS:
        pres, log = build_presence(lang, en_countries)
        allp[lang] = pres
        (OUT / f"presence.{lang}.json").write_text(json.dumps(pres, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        kinds = {k: sum(1 for d in pres.values() for e in d["entities"] if e["kind"] == k) for k in ("diplomatic", "order", "works")}
        print(f"{lang}: {len(pres)} countries, {sum(len(d['entities']) for d in pres.values())} entities {kinds}")
        for m in log:
            print(f"  {lang}: {m}")
    present = set().union(*[set(p) for p in allp.values()])
    svg, isos, nm = build_geometry(topo, present)
    (OUT / "world.svg").write_text(svg, encoding="utf-8")
    missing = sorted(present - set(isos))
    print(f"world.svg: {len(svg) / 1024:.0f} KB, {len(isos)} countries, {nm} markers; present but not in geometry: {missing}")


if __name__ == "__main__":
    main()
