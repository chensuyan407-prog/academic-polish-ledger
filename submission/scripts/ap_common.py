"""Shared helpers for academic-polish-ledger v0.2.0: robust reading (incl. stdlib .xlsx), format-aware
segmentation with offsets, protected tokens (math, citations, cross-references, URLs), lexicon matching and termbase loading.
Python 3.8+, standard library only (PyMuPDF optional for PDF input/preview)."""
import csv
import io
import json
import os
import re
import unicodedata
import xml.etree.ElementTree as ET
import zipfile

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_DIR = os.path.join(SKILL_DIR, "rules")
CJK = "\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"
KANA = "\u3040-\u30ff"
HANGUL = "\uac00-\ud7af"
TEXT_EXT = (".txt", ".md", ".markdown", ".tex", ".rst", ".text")


def load_json(path, default=None):
    if not path or not os.path.exists(path):
        return default
    with open(path, encoding="utf-8-sig") as fh:
        return json.load(fh)


def dump_json(obj, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)


def write_text(path, text):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


# ---------------------------------------------------------------- reading

MOJI_RUN = re.compile("[\u00c2-\u00f4][\u0080-\u00bf\u0152\u0153\u0160\u0161\u0178\u017d\u017e\u0192\u02c6\u02dc\u2013\u2014\u2018-\u201e\u2020-\u2022\u2026\u2030\u2039\u203a\u20ac\u2122]+")


def _mojibake_score(s):
    return len(re.findall("\ufffd|\u951f\u65a4\u62f7|\u00ef\u00bf\u00bd|[\x80-\x9f]", s)) + len(MOJI_RUN.findall(s))


def _repair_runs(text):
    """Reverse UTF-8-read-as-CP1252 damage run by run, so that correct non-Latin text elsewhere is untouched."""
    n = [0]

    def fix(m):
        seg = m.group(0)
        for enc in ("cp1252", "latin-1"):
            try:
                out = seg.encode(enc).decode("utf-8")
                n[0] += 1
                return out
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
        return seg
    return MOJI_RUN.sub(fix, text), n[0]


def decode_bytes(raw):
    """Decode bytes; returns (text, info). Tries UTF-8, UTF-16 (BOM), GB18030, CP1252 and repairs
    UTF-8-read-as-CP1252/Latin-1 mojibake. Every repair is reported, never silent."""
    info = {"encoding": None, "repairs": [], "replacement_chars": 0}
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        text, info["encoding"] = raw.decode("utf-16"), "utf-16"
    else:
        text = None
        for enc in ("utf-8-sig", "gb18030"):
            try:
                text = raw.decode(enc)
                info["encoding"] = enc
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            text = raw.decode("utf-8", errors="replace")
            info["encoding"] = "utf-8 (errors replaced)"
    before = _mojibake_score(text)
    if before >= 2:
        fixed, nrun = _repair_runs(text)
        if nrun and _mojibake_score(fixed) < before:
            info["repairs"].append(f"reversed UTF-8 read as CP1252 in {nrun} places ({before} -> {_mojibake_score(fixed)} suspicious sequences); check those words")
            text = fixed
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if "\u00a0" in text:
        info["repairs"].append(f"{text.count(chr(0xa0))} no-break spaces kept as-is")
    info["replacement_chars"] = text.count("\ufffd")
    info["mojibake_left"] = _mojibake_score(text)
    return text, info


def read_docx(path):
    """Paragraph text of a .docx (stdlib zip+XML). Run formatting is not kept."""
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    paras = []
    for p in re.findall(r"<w:p[ >].*?</w:p>", xml, flags=re.S):
        p = re.sub(r"<w:tab/>", "\t", p)
        p = re.sub(r"<w:br/>", "\n", p)
        t = "".join(re.findall(r"<w:t(?: [^>]*)?>(.*?)</w:t>", p, flags=re.S))
        t = t.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&apos;", "'").replace("&amp;", "&")
        paras.append(t)
    return "\n\n".join(x for x in paras if x.strip())


def read_pdf(path):
    try:
        import pymupdf as fitz  # noqa
    except ImportError:
        try:
            import fitz  # noqa
        except ImportError:
            fitz = None
    if fitz is not None:
        doc = fitz.open(path)
        if doc.needs_pass:
            raise ValueError("encrypted PDF")
        pages = []
        for page in doc:
            blocks = [b[4] for b in page.get_text("blocks") if b[6] == 0]
            pages.append("\n\n".join(re.sub(r"-\n(?=[a-z])", "", re.sub(r"(?<!\n)\n(?!\n)", " ", b)).strip() for b in blocks if b.strip()))
        return "\n\n".join(pages), {"pages": len(pages), "extractor": "pymupdf"}
    import subprocess
    r = subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True)
    if r.returncode != 0:
        raise ValueError("no PDF text extractor (install pymupdf or poppler-utils)")
    return r.stdout.decode("utf-8", errors="replace"), {"extractor": "pdftotext"}


def _xlsx_sheets(path):
    """Extract worksheet rows from .xlsx via stdlib zip+XML -> list of (sheet_name, rows)."""
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        shared = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall(".//{*}si"):
                shared.append("".join(t.text or "" for t in si.findall(".//{*}t")))
        sheet_names = {}
        if "xl/workbook.xml" in names and "xl/_rels/workbook.xml.rels" in names:
            wb = ET.fromstring(z.read("xl/workbook.xml"))
            rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
            rmap = {r.attrib.get("Id", ""): r.attrib.get("Target", "").lstrip("/") for r in rels}
            for sh in wb.findall(".//{*}sheet"):
                rid = next((v for k, v in sh.attrib.items() if k.endswith("}id") or k == "r:id"), "")
                tgt = rmap.get(rid, "")
                if tgt and not tgt.startswith("xl/"):
                    tgt = "xl/" + tgt
                if tgt:
                    sheet_names[tgt] = sh.attrib.get("name", os.path.basename(tgt))
        sfiles = sorted(n for n in names if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n))
        sheets = []
        for sf in sfiles:
            root = ET.fromstring(z.read(sf))
            rows = []
            for row in root.findall(".//{*}row"):
                cells = {}
                max_col = -1
                for c in row.findall("{*}c"):
                    ref = c.attrib.get("r", "")
                    mcol = re.match(r"([A-Z]+)", ref)
                    if mcol:
                        idx = 0
                        for ch in mcol.group(1):
                            idx = idx * 26 + (ord(ch) - 64)
                        idx -= 1
                    else:
                        idx = max_col + 1
                    max_col = max(max_col, idx)
                    ctype = c.attrib.get("t", "")
                    val = ""
                    if ctype == "inlineStr":
                        val = "".join(t.text or "" for t in c.findall(".//{*}t"))
                    else:
                        v = c.find("{*}v")
                        if v is not None and v.text is not None:
                            if ctype == "s" and v.text.isdigit() and int(v.text) < len(shared):
                                val = shared[int(v.text)]
                            elif ctype == "b":
                                val = "TRUE" if v.text == "1" else "FALSE"
                            else:
                                val = v.text
                    cells[idx] = val.strip()
                if any(cells.values()):
                    rows.append([cells.get(i, "") for i in range(max_col + 1)])
            if rows:
                sheets.append((sheet_names.get(sf, os.path.basename(sf)), rows))
        return sheets


def read_xlsx(path):
    """Render .xlsx sheets as Markdown tables via stdlib zip+XML."""
    sheets = _xlsx_sheets(path)
    out = []
    for title, rows in sheets:
        w = max(len(r) for r in rows)
        norm = [r + [""] * (w - len(r)) for r in rows]
        out.append(f"## {title}")
        out.append("| " + " | ".join(c.replace("|", "/") for c in norm[0]) + " |")
        out.append("| " + " | ".join(["---"] * w) + " |")
        for r in norm[1:]:
            out.append("| " + " | ".join(c.replace("|", "/") for c in r) + " |")
        out.append("")
    return "\n".join(out).strip()


def read_any(path):
    """Return (text, fmt, info). fmt in txt|md|tex|docx|pdf|json."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".docx":
        return read_docx(path), "docx", {"encoding": "docx-xml", "repairs": ["run-level formatting not preserved"]}
    if ext == ".xlsx":
        return read_xlsx(path), "md", {"encoding": "xlsx-xml", "repairs": []}
    if ext == ".pdf":
        text, info = read_pdf(path)
        info["repairs"] = ["text extracted from PDF layout; line breaks and hyphenation reconstructed"]
        return text, "pdf", info
    with open(path, "rb") as fh:
        raw = fh.read()
    text, info = decode_bytes(raw)
    fmt = {".md": "md", ".markdown": "md", ".tex": "tex", ".json": "json"}.get(ext, "txt")
    if fmt == "txt" and re.search(r"\\(?:section|begin|cite|documentclass)\b", text):
        fmt = "tex"
    elif fmt == "txt" and re.search(r"(?m)^#{1,6} \S|^\s*[-*] \S|\*\*\S", text):
        fmt = "md"
    return text, fmt, info


# ---------------------------------------------------------------- language

def lang_of(text):
    cjk = len(re.findall(f"[{CJK}]", text))
    lat = len(re.findall(r"[A-Za-z]", text))
    kana = len(re.findall(f"[{KANA}]", text))
    if kana >= 3 and kana >= 0.1 * (cjk + 1):
        return "ja"
    if len(re.findall(f"[{HANGUL}]", text)) >= 3:
        return "ko"
    if cjk >= 2 and cjk * 2 >= lat * 0.5:
        return "zh"
    return "en" if lat else ("zh" if cjk else "other")


# ---------------------------------------------------------------- protected tokens

PROTECT_PATTERNS = [
    ("math", r"\$\$.+?\$\$|\$[^$\n]+?\$|\\\(.+?\\\)|\\\[.+?\\\]"),
    ("latex_cmd", r"\\(?:cite[a-zA-Z]*|ref|eqref|autoref|cref|Cref|pageref|label|url|href|footnote|SI|si|num|unit|ce)\*?(?:\[[^\]]*\])*\{[^{}]*\}(?:\{[^{}]*\})?"),
    ("latex_cmd", r"\\[a-zA-Z]+\*?(?:\{[^{}]*\})?"),
    ("url", r"https?://\S+|doi:\s*\S+|\b10\.\d{4,9}/[^\s,;)]+"),
    ("citation", r"\[(?:\d+[a-z]?(?:\s*[-–—,]\s*\d+[a-z]?)*)\]|［\d+(?:[-–,，]\d+)*］|\^\{?\[?\d+(?:[-–,]\d+)*\]?\}?"),
    ("citation", r"\((?:see |cf\. |e\.g\., )?[A-Z][A-Za-z'\-]+(?: (?:et al\.|and|&) ?[A-Z]?[A-Za-z'\-]*)?,? (?:19|20)\d{2}[a-z]?(?:[;,] ?(?:[A-Z][A-Za-z'\-]+(?: (?:et al\.|and|&) ?[A-Z]?[A-Za-z'\-]*)?,? )?(?:19|20)\d{2}[a-z]?)*\)"),
    ("citation", r"\b[A-Z][A-Za-z'\-]+ (?:et al\.|and [A-Z][A-Za-z'\-]+) \((?:19|20)\d{2}[a-z]?\)"),
    ("xref", r"\b(?:Figs?\.|Figures?|Tables?|Tabs?\.|Eqs?\.|Equations?|Sections?|Secs?\.|Supplementary (?:Figures?|Tables?|Notes?|Figs?\.)|Algorithms?|Appendix|Theorem|Lemma|Ref\.|Refs\.)\s*~?(?:\(\d+[a-z]?\)|[SA]?\d+(?:\.\d+)*[a-z]?(?:\([a-z]\))?)(?:\s*(?:[-–,]|and)\s*(?:\(\d+[a-z]?\)|[SA]?\d+(?:\.\d+)*[a-z]?(?:\([a-z]\))?))*"),
    ("xref", r"(?:图|表|式|公式|方程|附图|附表|第)\s*(?:[（(]\d+[a-z]?[）)]|[SA]?\d+(?:[.\-–]\d+)*[a-z]?)(?:\s*[章节部分])?"),
]
_PROTECT_RE = [(k, re.compile(p, re.S)) for k, p in PROTECT_PATTERNS]


def protected_spans(text):
    """Non-overlapping (start, end, kind, token) spans that must survive polishing unchanged."""
    spans = []
    for kind, rx in _PROTECT_RE:
        for m in rx.finditer(text):
            s, e = m.span()
            if e <= s or any(not (e <= a or s >= b) for a, b, _, _ in spans):
                continue
            spans.append((s, e, kind, m.group(0)))
    spans.sort()
    return spans


def protected_tokens(text):
    """Multiset view for comparison: kind -> list of normalised tokens."""
    out = {}
    for s, e, kind, tok in protected_spans(text):
        if kind == "latex_cmd" and not re.match(r"\\(?:cite|ref|eqref|autoref|cref|Cref|label|SI|si|num|ce)", tok):
            continue
        out.setdefault(kind, []).append(norm_token(tok, kind))
    return out


def norm_token(tok, kind):
    t = unicodedata.normalize("NFKC", tok).replace("–", "-").replace("—", "-").replace("~", " ")
    if kind == "xref":
        # map the label word first (while the space before the number still separates 'Table S2' from 'Tables 2')
        t = t.lower().strip()
        t = re.sub(r"^supplementary\s+(?:figures?|figs?\.?)\s*", "suppfig:", t)
        t = re.sub(r"^supplementary\s+(?:tables?|tabs?\.?)\s*", "supptable:", t)
        t = re.sub(r"^supplementary\s+notes?\s*", "suppnote:", t)
        t = re.sub(r"^(?:figures?|figs?\.?)\s*", "fig:", t)
        t = re.sub(r"^(?:tables?|tabs?\.?)\s*", "table:", t)
        t = re.sub(r"^(?:equations?|eqs?\.?)\s*", "eq:", t)
        t = re.sub(r"^(?:sections?|secs?\.?)\s*", "sec:", t)
        t = re.sub(r"^(?:公式|方程)\s*", "式", t)
        t = t.replace("（", "(").replace("）", ")")
    return re.sub(r"\s+", "", t)


# ---------------------------------------------------------------- numbers

EN_NUMWORDS = {"zero": 0, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
               "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
               "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
               "hundred": 100, "thousand": 1000, "twofold": 2, "threefold": 3, "fourfold": 4, "fivefold": 5, "tenfold": 10,
               "half": 0.5, "double": 2, "twice": 2, "triple": 3, "thrice": 3, "dozen": 12}
ZH_DIGIT = {"二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10, "百": 100, "千": 1000, "半": 0.5}
ZH_CLASSIFIER = "个种组次项名例只篇类倍批天周年月份位台套层株轮步阶"
NUM_RE = re.compile(r"(?<![A-Za-z0-9_.])[-−–+±]?\d{1,3}(?:,\d{3})+(?:\.\d+)?(?![\d])|(?<![A-Za-z0-9_.])[-−+±]?\d+(?:\.\d+)?(?:\s*[×x]\s*10\s*\^?\s*\{?[-−]?\d+\}?|[eE][-+]?\d+)?")
UNIT_RE = re.compile(r"(?:[\s\u00a0]|-(?=[A-Za-zµμ°%]))?(%|‰|°C|°|℃|K(?![A-Za-z])|nm(?![A-Za-z])|µm(?![A-Za-z])|μm(?![A-Za-z])|mm(?![A-Za-z])|cm(?![A-Za-z])|m(?![A-Za-z])|km(?![A-Za-z])|mg(?![A-Za-z])|g(?![A-Za-z])|kg(?![A-Za-z])|µg(?![A-Za-z])|μg(?![A-Za-z])|ng(?![A-Za-z])|mL(?![A-Za-z])|ml(?![A-Za-z])|L(?![A-Za-z])|µL(?![A-Za-z])|μL(?![A-Za-z])|mM(?![A-Za-z])|µM(?![A-Za-z])|μM(?![A-Za-z])|nM(?![A-Za-z])|M(?![A-Za-z])|mol(?![A-Za-z])|eV(?![A-Za-z])|meV(?![A-Za-z])|keV(?![A-Za-z])|MeV(?![A-Za-z])|Hz(?![A-Za-z])|kHz(?![A-Za-z])|MHz(?![A-Za-z])|GHz(?![A-Za-z])|THz(?![A-Za-z])|Pa(?![A-Za-z])|kPa(?![A-Za-z])|MPa(?![A-Za-z])|GPa(?![A-Za-z])|V(?![A-Za-z])|mV(?![A-Za-z])|A(?![A-Za-z])|mA(?![A-Za-z])|W(?![A-Za-z])|mW(?![A-Za-z])|kW(?![A-Za-z])|J(?![A-Za-z])|kJ(?![A-Za-z])|s(?![A-Za-z])|ms(?![A-Za-z])|min(?![A-Za-z])|h(?![A-Za-z])|d(?![A-Za-z])|days?(?![A-Za-z])|weeks?(?![A-Za-z])|months?(?![A-Za-z])|years?(?![A-Za-z])|fold(?![A-Za-z])|times(?![A-Za-z])|倍|个|例|名|天|小时|分钟|年|月)")


def _num_value(tok):
    t = tok.replace(",", "").replace("−", "-").replace("–", "-").replace("±", "").replace("+", "")
    m = re.match(r"(-?\d+(?:\.\d+)?)(?:\s*[×x]\s*10\s*\^?\s*\{?(-?\d+)\}?|[eE]([-+]?\d+))?$", t.strip())
    if not m:
        return t.strip()
    v = float(m.group(1))
    ex = m.group(2) or m.group(3)
    if ex:
        v *= 10 ** int(ex.replace("−", "-"))
    return round(v, 10)


def numbers(text, lang=None):
    """List of (value, unit, raw) for numbers outside protected spans (citations/xrefs/math are checked separately).
    Number words (two..twenty, twofold, 两/三...+classifier) are normalised to values, so '3' -> 'three' is not a change."""
    masked = list(text)
    for s, e, kind, _ in protected_spans(text):
        for i in range(s, e):
            masked[i] = " "
    t = "".join(masked)
    out = []
    for m in NUM_RE.finditer(t):
        raw = m.group(0)
        um = UNIT_RE.match(t, m.end())
        unit = um.group(1) if um else ""
        unit = {"℃": "°C", "μm": "µm", "μg": "µg", "μL": "µL", "μM": "µM", "ml": "mL", "day": "days", "week": "weeks", "month": "months", "year": "years"}.get(unit, unit)
        out.append((_num_value(raw), unit, raw.strip()))
    for m in re.finditer(r"\b(" + "|".join(EN_NUMWORDS) + r")\b", t, flags=re.I):
        w = m.group(1).lower()
        if w in ("half", "double", "dozen") and not re.match(r"\s+(?:the|of|as|a)\b", t[m.end():m.end() + 6]) and w != "dozen":
            continue
        u = "fold" if w in ("twice", "twofold", "threefold", "fourfold", "fivefold", "tenfold") else ""
        out.append((float(EN_NUMWORDS[w]), u, m.group(0)))
    for m in re.finditer(f"([二两三四五六七八九十百千半]+)(?=[{ZH_CLASSIFIER}])", t):
        v = 0
        tok = m.group(1)
        if tok in ZH_DIGIT:
            v = ZH_DIGIT[tok]
        elif re.fullmatch("十[二三四五六七八九]", tok):
            v = 10 + ZH_DIGIT[tok[1]]
        elif re.fullmatch("[二三四五六七八九]十", tok):
            v = ZH_DIGIT[tok[0]] * 10
        else:
            continue
        out.append((float(v), "", tok))
    return out


# ---------------------------------------------------------------- segmentation

ABBREV = r"(?:e\.g|i\.e|et al|etc|vs|cf|approx|Fig|Figs|Eq|Eqs|Ref|Refs|Sec|Secs|No|Nos|Dr|Mr|Mrs|Ms|Prof|Jr|Sr|St|Inc|Ltd|Co|Corp|resp|ca|viz|al|Vol|vol|pp|p|ed|eds|Tab|Suppl|Supp|ibid|cit|op|Ph\.D|M\.S|B\.S|U\.S|U\.K|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|Mt|var|min|max|wt|vol)\."


def split_sentences(text, base=0):
    """Return list of (start, end) sentence spans within text (offsets + base). Boundaries are never placed
    inside protected spans (math, citations, cross-references)."""
    prot = protected_spans(text)
    blocked = bytearray(len(text) + 1)
    for s, e, _, _ in prot:
        for i in range(s, min(e, len(text))):
            blocked[i] = 1
    cuts = []
    for m in re.finditer(r"[.!?](?:[\"'”’)\]]*)(?=\s+[\"'“‘(\[]?[A-Z0-9\u4e00-\u9fff$\\])|[。！？](?:[”’」』）)]*)|[;；](?=\s*\n)", text):
        end = m.end()
        pos = m.start()
        if blocked[pos]:
            continue
        if text[pos] == ".":
            pre = text[max(0, pos - 12):pos + 1]
            if re.search(r"(?:^|[\s(\[])" + ABBREV + r"$", pre) or re.search(r"(?:^|\s)[A-Z]\.$", pre) or re.search(r"\d\.$", pre) and re.match(r"\s*\d", text[end:end + 3]):
                continue
        cuts.append(end)
    spans, start = [], 0
    for c in cuts + [len(text)]:
        seg = text[start:c]
        if seg.strip():
            ls = len(seg) - len(seg.lstrip())
            rs = len(seg.rstrip())
            spans.append((base + start + ls, base + start + rs))
        start = c
    return spans


def _blocks(text, fmt):
    """Yield (start, end, kind) for blocks. kind: prose | heading | skip (code, math env, tables, preamble, comments)."""
    out = []
    if fmt == "tex":
        skip = []
        body = re.search(r"\\begin\{document\}", text)
        if body:
            skip.append((0, body.end()))
        enddoc = re.search(r"\\end\{document\}", text)
        if enddoc:
            skip.append((enddoc.start(), len(text)))
        for m in re.finditer(r"\\begin\{(equation|align|gather|multline|eqnarray|displaymath|math|tabular|tikzpicture|lstlisting|verbatim|minted|algorithmic|algorithm|thebibliography|figure|table)\*?\}.*?\\end\{\1\*?\}", text, flags=re.S):
            skip.append(m.span())
        for m in re.finditer(r"(?m)(?<!\\)%.*$", text):
            skip.append(m.span())
        for m in re.finditer(r"(?m)^\s*\\(?:documentclass|usepackage|maketitle|bibliography|bibliographystyle|begin|end|label|includegraphics|centering|newcommand|renewcommand|item(?=\s*$))\b.*$", text):
            skip.append(m.span())
        for m in re.finditer(r"\\(?:section|subsection|subsubsection|paragraph|chapter|title|caption)\*?\{", text):
            # heading/caption argument is prose; the command itself is skipped
            skip.append((m.start(), m.end()))
            depth, i = 1, m.end()
            while i < len(text) and depth:
                depth += {"{": 1, "}": -1}.get(text[i], 0)
                i += 1
            out.append((m.end(), i - 1, "heading" if "caption" not in m.group(0) else "prose"))
            skip.append((i - 1, i))
        skip.sort()
        merged = []
        for s, e in skip:
            if merged and s <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(e, merged[-1][1]))
            else:
                merged.append((s, e))
        heads = [(s, e) for s, e, _ in out]
        pos = 0
        for s, e in merged + [(len(text), len(text))]:
            if s > pos:
                _para_blocks(text, pos, s, out, exclude=heads)
            pos = max(pos, e)
        out.sort()
        return out
    if fmt == "md":
        pos = 0
        for m in re.finditer(r"(?ms)^```.*?^```[^\n]*$|^\$\$.*?\$\$|^(?:\|.*\|\s*\n)+|^<!--.*?-->|^---\n.*?\n---\n", text):
            if m.start() > pos:
                _para_blocks(text, pos, m.start(), out, md=True)
            pos = m.end()
        _para_blocks(text, pos, len(text), out, md=True)
        return out
    _para_blocks(text, 0, len(text), out)
    return out


def _para_blocks(text, s, e, out, md=False, exclude=()):
    for m in re.finditer(r"(?:[^\n]|\n(?!\s*\n))+", text[s:e]):
        a, b = s + m.start(), s + m.end()
        if any(not (b <= x or a >= y) for x, y in exclude):
            continue
        chunk = text[a:b]
        lead = len(chunk) - len(chunk.lstrip())
        a += lead
        chunk = chunk.strip()
        if not chunk:
            continue
        if md:
            hm = re.match(r"#{1,6}\s+", chunk)
            if hm:
                out.append((a + hm.end(), b, "heading"))
                continue
            lm = re.match(r"(?:[-*+]|\d+[.)])\s+", chunk)
            if lm:
                # list: each item a block
                for im in re.finditer(r"(?m)^\s*(?:[-*+]|\d+[.)])\s+(.*(?:\n(?!\s*(?:[-*+]|\d+[.)])\s).*)*)", chunk):
                    out.append((a + im.start(1), a + im.end(1), "prose"))
                continue
            qm = re.match(r">\s*", chunk)
            if qm:
                a += qm.end()
        if re.fullmatch(r"[\W\d_]+", chunk):
            continue
        if not md and len(chunk) < 90 and "\n" not in chunk and not re.search(r"[.。!?！？:：;；]$", chunk) and re.match(r"(?:\d+(?:\.\d+)*\.?\s+|第.{1,3}[章节]\s*|[一二三四五六七八九十]+[、.]\s*|(?:Abstract|Introduction|Methods?|Results?|Discussion|Conclusions?|References|Acknowledg\w+|摘要|引言|方法|结果|讨论|结论|参考文献)\b)", chunk):
            out.append((a, b, "heading"))
            continue
        out.append((a, b, "prose"))


def segment(text, fmt, doc_prefix=""):
    """Segments with stable ids p<para>.s<sent> (heading blocks: h<n>). Offsets point into the original text."""
    segs = []
    pn = hn = 0
    for a, b, kind in _blocks(text, fmt):
        if kind == "heading":
            hn += 1
            segs.append({"sid": f"{doc_prefix}h{hn}", "start": a, "end": b, "kind": "heading", "para": None})
            continue
        pn += 1
        sents = split_sentences(text[a:b], base=a)
        for k, (s, e) in enumerate(sents, 1):
            segs.append({"sid": f"{doc_prefix}p{pn}.s{k}", "start": s, "end": e, "kind": "sentence", "para": pn})
    for sg in segs:
        sg["text"] = text[sg["start"]:sg["end"]]
        sg["lang"] = lang_of(sg["text"])
    return segs


# ---------------------------------------------------------------- lexicon

_LEX_CACHE = {}


def lexicon():
    if "lex" not in _LEX_CACHE:
        raw = load_json(os.path.join(RULES_DIR, "lexicon.json"))
        lex = {}
        for cls, d in raw.items():
            if cls.startswith("_"):
                continue
            en = [p for p in d.get("en", [])]
            zh = [p for p in d.get("zh", [])]
            ent = {"level": d.get("level")}
            ent["en"] = re.compile(r"(?<![\w-])(?:" + "|".join(sorted(en, key=len, reverse=True)) + r")(?![\w-])", re.I) if en else None
            ent["zh"] = re.compile("(?:" + "|".join(sorted(zh, key=len, reverse=True)) + ")") if zh else None
            ent["ex_en"] = re.compile(r"(?<![\w-])(?:" + "|".join(d["exclude_en"]) + r")(?![\w-])", re.I) if d.get("exclude_en") else None
            ent["ex_zh"] = re.compile("(?:" + "|".join(d["exclude_zh"]) + ")") if d.get("exclude_zh") else None
            ent["number_bound"] = d.get("number_bound", False)
            lex[cls] = ent
        _LEX_CACHE["lex"] = lex
    return _LEX_CACHE["lex"]


def _strip_protected(text):
    chars = list(text)
    for s, e, _, _ in protected_spans(text):
        for i in range(s, e):
            chars[i] = " "
    return "".join(chars)


def lexical_hits(text, mask_terms=()):
    """class -> list of matched words (lower-case), excluding protected spans, excluded phrases and termbase terms
    (so '首次库伦效率' or 'non-linear' inside a defined term is not read as a novelty claim or a negation)."""
    t = _strip_protected(text)
    for term in mask_terms:
        rx = term_regex(term) if term and len(term) > 1 else None
        if rx:
            t = rx.sub(lambda m: " " * len(m.group(0)), t)
    lex = lexicon()
    out = {}
    for cls, ent in lex.items():
        hits = []
        for key, exkey in (("en", "ex_en"), ("zh", "ex_zh")):
            rx = ent[key]
            if rx is None:
                continue
            ex_spans = [m.span() for m in ent[exkey].finditer(t)] if ent[exkey] else []
            for m in rx.finditer(t):
                if any(a <= m.start() < b for a, b in ex_spans):
                    continue
                if ent["number_bound"] and not re.match(r"\s*[-−~]?\s*(?:\d|[二两三四五六七八九十百千半]|" + "|".join(EN_NUMWORDS) + r")", t[m.end():m.end() + 12], flags=re.I) \
                        and not (key == "zh" and m.group(0) in ("左右", "以上", "以下", "上下") and re.search(r"\d\s*\S{0,3}$", t[max(0, m.start() - 8):m.start()])):
                    continue
                hits.append(m.group(0).lower())
        if hits:
            out[cls] = hits
    return out


# ---------------------------------------------------------------- termbase

def _norm_term(t):
    t = unicodedata.normalize("NFKC", t).lower().strip()
    return re.sub(r"[\s\-‐‑–_]+", " ", t)


def load_termbase(path_or_obj):
    """Accepts csv/tsv/json/md-table file or an inline list/dict. Returns list of entries
    {preferred, variants[], zh, en, abbr, note, source}. Column names are matched loosely
    (preferred/term/标准译名/推荐, variants/avoid/禁用/不推荐, zh/中文, en/英文/English, abbr/缩写)."""
    rows, src = [], None
    if isinstance(path_or_obj, str) and os.path.exists(path_or_obj):
        src = os.path.basename(path_or_obj)
        ext = os.path.splitext(path_or_obj)[1].lower()
        if ext == ".xlsx":
            for _, srows in _xlsx_sheets(path_or_obj):
                if len(srows) >= 2:
                    head = [c.strip() for c in srows[0]]
                    for r in srows[1:]:
                        rows.append(dict(zip(head, r)))
        else:
            text, _, _ = read_any(path_or_obj) if ext not in (".csv", ".tsv") else (decode_bytes(open(path_or_obj, "rb").read())[0], None, None)
            if ext == ".json":
                obj = json.loads(text)
                return load_termbase(obj) if not isinstance(obj, str) else []
            if ext in (".csv", ".tsv") or (text.count("\t") > text.count("|")):
                dialect = "excel-tab" if (ext == ".tsv" or text.count("\t") > text.count(",")) else "excel"
                rows = list(csv.DictReader(io.StringIO(text), dialect=dialect))
            else:
                lines = [l for l in text.splitlines() if l.strip().startswith("|")]
                if len(lines) >= 2:
                    head = [c.strip() for c in lines[0].strip().strip("|").split("|")]
                    for l in lines[1:]:
                        cells = [c.strip() for c in l.strip().strip("|").split("|")]
                        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                            continue
                        rows.append(dict(zip(head, cells)))
                else:
                    for l in text.splitlines():
                        m = re.match(r"\s*[-*]?\s*(.+?)\s*(?:=>|->|→|:|：|=)\s*(.+)$", l)
                        if m:
                            rows.append({"variants": m.group(1), "preferred": m.group(2)})
    elif isinstance(path_or_obj, dict):
        if "terms" in path_or_obj or "entries" in path_or_obj:
            return load_termbase(path_or_obj.get("terms") or path_or_obj.get("entries"))
        rows = [{"variants": k, "preferred": v} if isinstance(v, str) else dict(v, term=k) for k, v in path_or_obj.items()]
        src = "inline"
    elif isinstance(path_or_obj, list):
        rows = [r if isinstance(r, dict) else {"preferred": str(r)} for r in path_or_obj]
        src = "inline"
    entries = []
    for r in rows:
        low = {str(k).strip().lower(): (v if isinstance(v, (list, dict)) else str(v or "").strip()) for k, v in r.items() if k is not None}

        var_keys = [k for k in low if re.search(r"variant|avoid|deprecat|synonym|alias|wrong|禁用|不推荐|避免|变体|别名|错误|非标准|不规范", k)]

        def pick(*names, skip=()):
            for n in names:
                for k, v in low.items():
                    if k in skip:
                        continue
                    if k == n or ((len(n) > 2 or re.search(f"[{CJK}]", n)) and n in k):
                        if v:
                            return v
            return ""
        rest = tuple(var_keys)
        en = pick("en", "english", "英文", "target", "译名", skip=rest)
        zh = pick("zh", "chinese", "中文", "source", "原文", skip=rest)
        pref = pick("preferred", "standard", "推荐", "标准", "统一", "use", "规范", skip=rest) or en or pick("term", "术语", skip=rest) or zh
        var = [low[k] for k in var_keys if low[k]]
        var = var[0] if len(var) == 1 else ";".join(x if isinstance(x, str) else ";".join(x) for x in var)
        if isinstance(var, str):
            var = [v.strip() for v in re.split(r"[;；,，/|、]", var) if v.strip()]
        abbr = pick("abbr", "abbreviation", "缩写", "acronym", skip=rest)
        note = pick("note", "notes", "备注", "说明", "definition", "定义", skip=rest)
        if isinstance(pref, list):
            pref = pref[0] if pref else ""
        if not pref:
            continue
        entries.append({"preferred": pref, "variants": [v for v in var if _norm_term(v) != _norm_term(pref)], "zh": zh if zh != pref else (zh or ""),
                        "en": en, "abbr": abbr if isinstance(abbr, str) else "", "note": note if isinstance(note, str) else "", "source": src or "inline"})
    return entries


def termbase_conflicts(entries):
    """Internal conflicts: one variant mapped to different preferred terms; a preferred term listed as a variant elsewhere;
    one source (zh) term with two different targets; one abbreviation for two terms."""
    conf = []
    by_var, by_zh, by_abbr = {}, {}, {}
    prefs = {_norm_term(e["preferred"]): e for e in entries}
    for e in entries:
        for v in e["variants"]:
            by_var.setdefault(_norm_term(v), set()).add(e["preferred"])
            if _norm_term(v) in prefs and prefs[_norm_term(v)]["preferred"] != e["preferred"]:
                conf.append({"type": "variant_is_preferred_elsewhere", "term": v, "entries": [e["preferred"], prefs[_norm_term(v)]["preferred"]]})
        if e.get("zh"):
            by_zh.setdefault(_norm_term(e["zh"]), set()).add(e["preferred"])
        if e.get("abbr"):
            by_abbr.setdefault(e["abbr"].strip(), set()).add(e["preferred"])
    for v, ps in by_var.items():
        if len(ps) > 1:
            conf.append({"type": "variant_maps_to_several", "term": v, "entries": sorted(ps)})
    for z, ps in by_zh.items():
        if len(ps) > 1:
            conf.append({"type": "source_term_two_targets", "term": z, "entries": sorted(ps)})
    for a, ps in by_abbr.items():
        if len(ps) > 1:
            conf.append({"type": "abbreviation_two_terms", "term": a, "entries": sorted(ps)})
    return conf


def term_regex(term):
    """Regex for a term that tolerates hyphen/space variation and case; word-bounded for Latin terms."""
    parts = [re.escape(p) for p in re.split(r"[\s\-‐‑–_]+", term.strip()) if p]
    if not parts:
        return None
    body = r"[\s\-‐‑–_]?".join(parts) if re.search(f"[{CJK}]", term) else r"[\s\-‐‑–_]+".join(parts)
    if re.search(r"[A-Za-z0-9]", term):
        if re.search(r"[^aeiou]y$", parts[-1], flags=re.I):
            body = body[:-1] + "(?:y|ies)"
        return re.compile(r"(?<![A-Za-z0-9-])" + body + r"(?:s|es)?(?![A-Za-z0-9-])", re.I)
    return re.compile(body)


def abbreviation_definitions(text):
    """'full form (ABBR)' and '中文全称（英文全称, ABBR）' style definitions -> list of (abbr, long, offset)."""
    out = []
    for m in re.finditer(r"([A-Za-z][A-Za-z\-]*(?:\s+[A-Za-z][A-Za-z\-]*){0,7})\s*[(（]\s*([A-Z][A-Za-z0-9\-]*[A-Z0-9][s]?)\s*[)）]", text):
        abbr, longf = m.group(2), m.group(1)
        letters = re.sub(r"[^A-Z]", "", abbr)
        words = re.split(r"[\s\-]+", longf)
        cand = words[-max(len(letters), 1):]
        # accept if initials roughly match
        initials = "".join(w[0].upper() for w in words[-len(letters) - 2:] if w)
        if len(letters) >= 2 and (all(c in initials for c in letters[:2]) or longf.lower().startswith(abbr[0].lower())):
            n = len(letters)
            best = " ".join(words[-n:]) if len(words) >= n else longf
            for k in range(n - 1, min(len(words), n + 3) + 1):
                cw = words[-k:]
                if cw and cw[0][0].upper() == letters[0]:
                    best = " ".join(cw)
                    break
            out.append((abbr, best, m.start()))
    for m in re.finditer(f"([{CJK}]{{2,20}})[（(]\\s*(?:[A-Za-z][A-Za-z\\-\\s]+,\\s*)?([A-Z][A-Za-z0-9\\-]*[A-Z0-9])\\s*[)）]", text):
        out.append((m.group(2), m.group(1), m.start()))
    return out
