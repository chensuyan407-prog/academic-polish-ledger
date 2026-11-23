#!/usr/bin/env python3
"""Invariant checks for academic polishing: does the revised sentence still say what the original said?

Per sentence (original vs revised):
  I01 numbers + units   I02 citation markers   I03 figure/table/equation/section references   I04 math + LaTeX commands
  I05 hedge strength    I06 boosters added     I07 approximators (about, ~, 约)              I08 significance wording
  I09 novelty/promotional wording               I10 negation   I11 quantifiers (all/most/some/only)
  I12 causal vs correlational wording            I13 conditions (if, under ... conditions, 在…条件下)
  I14 direction words (increase/decrease)
Change records:
  R01 record not verifiable (from/to not found, no reason)   R02 change in the text without a record
  R03 heavy rewrite (minimal-edit principle)                 R04 residual style problem still present
  R05 record without effect / unknown change type
Document level (doc_checks): D01 termbase variant used  D02 source term not rendered with its target (translation)
  D03 abbreviation defined late/twice/never   D04 hyphen/case drift of one term   D05 mixed US/UK spelling

Standalone use on any two versions (e.g. to audit another tool's rewrite):
  python ap_check.py --orig original.md --rev revised.md [--mode polish|translate] [--termbase terms.csv] [--json out.json]
"""
import argparse
import difflib
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ap_common import (CJK, _norm_term, abbreviation_definitions, lexical_hits, load_termbase, numbers,  # noqa: E402
                       protected_tokens, read_any, segment, term_regex, termbase_conflicts)
from ap_lint import lint  # noqa: E402

CHANGE_TYPES = {"grammar", "agreement", "number-agreement", "tense", "voice", "article", "preposition", "collocation",
                "word-choice", "spelling", "punctuation", "format", "terminology", "abbreviation", "register", "tone",
                "hedging", "concision", "redundancy", "chinglish", "clarity", "sentence-split", "merge", "restructure",
                "reorder", "translation", "consistency", "style", "other", "subject", "connective", "typo"}
HEAVY_OK = {"sentence-split", "merge", "restructure", "reorder", "translation", "chinglish", "subject", "clarity"}
INFERENTIAL = {"therefore", "thus", "hence", "consequently", "as a result", "因此", "所以", "从而", "进而"}
FAIL, WARN, INFO = "fail", "warn", "info"
UNIT_EQ = {"倍": "fold", "times": "fold", "天": "days", "年": "years", "月": "months", "小时": "h", "分钟": "min",
           "个": "", "例": "", "名": "", "d": "days", "℃": "°C"}
TRANSLATE_SOFT = {"I10", "I11u", "I13", "I14"}


def _ms(lst):
    return Counter(lst)


def _diff_ms(a, b):
    ca, cb = _ms(a), _ms(b)
    return sorted((ca - cb).elements(), key=str), sorted((cb - ca).elements(), key=str)


def _xref_norm(t):
    """Language-neutral reference key: 'Fig. S5' / '图S5' -> 'fig:s5', 'Table 2' / '表2' -> 'table:2', 'Eq. (3)' / '式(3)' -> 'eq:3'.
    Supplementary prefixes are kept, so 'Table S2' never equals 'Table 2'."""
    t = t.replace("(", "").replace(")", "")
    t = re.sub(r"^附图", "suppfig:", t)
    t = re.sub(r"^附表", "supptable:", t)
    t = re.sub(r"^图", "fig:", t)
    t = re.sub(r"^表", "table:", t)
    t = re.sub(r"^式", "eq:", t)
    t = re.sub(r"^第(\d+(?:\.\d+)*)[章节部分]", r"sec:\1", t)
    return t


def tokens(text):
    return re.findall(f"[{CJK}]|[A-Za-z0-9_]+(?:['’][a-z]+)?|\\s+|[^\\w\\s]", text)


def hunks(orig, rev):
    """Changed regions as (orig_start, orig_end, rev_start, rev_end, orig_text, rev_text), whitespace-only hunks dropped."""
    ta, tb = tokens(orig), tokens(rev)
    oa, ob = [0], [0]
    for t in ta:
        oa.append(oa[-1] + len(t))
    for t in tb:
        ob.append(ob[-1] + len(t))
    sm = difflib.SequenceMatcher(None, ta, tb, autojunk=False)
    out = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            continue
        a, b = orig[oa[i1]:oa[i2]], rev[ob[j1]:ob[j2]]
        if not a.strip() and not b.strip():
            continue
        out.append((oa[i1], oa[i2], ob[j1], ob[j2], a, b))
    return out, sm.ratio(), len(ta)


def _find_all(hay, needle):
    if not needle:
        return []
    spans = [(m.start(), m.end()) for m in re.finditer(re.escape(needle), hay)]
    if spans:
        return spans
    rx = re.escape(re.sub(r"\s+", " ", needle.strip())).replace(r"\ ", r"\s+")
    return [(m.start(), m.end()) for m in re.finditer(rx, hay, flags=re.I)]


def _hedge_level(h):
    lv = [1] if h.get("hedge_weak") else []
    if h.get("hedge_moderate"):
        lv.append(2)
    return min(lv) if lv else None


def check_pair(orig, rev, mode="polish", records=None, accept=None, genre=None, lang=None, mask_terms=()):
    """Return list of findings {code, severity, detail}. records = change records of this unit; accept = {code: reason}."""
    f = []
    translate = mode.startswith("translate")

    def add(code, sev, detail):
        if translate and code in TRANSLATE_SOFT and sev == FAIL:
            sev = WARN
        f.append({"code": code, "severity": sev, "detail": detail})

    # I01 numbers
    na, nb = numbers(orig), numbers(rev)
    va, vb = [n[0] for n in na], [n[0] for n in nb]
    lost, new = _diff_ms(va, vb)
    if lost or new:
        add("I01", FAIL, f"numbers changed: missing {lost or '[]'}, added {new or '[]'}")
    else:
        ua = Counter((v, UNIT_EQ.get(u, u)) for v, u, _ in na)
        ub = Counter((v, UNIT_EQ.get(u, u)) for v, u, _ in nb)
        if ua != ub and not translate:
            l2, n2 = sorted((ua - ub).elements(), key=str), sorted((ub - ua).elements(), key=str)
            if any(u for _, u in l2 + n2):
                add("I01", FAIL, f"unit changed: {l2} -> {n2}")
    pa, pb = protected_tokens(orig), protected_tokens(rev)
    for p in (pa, pb):  # LaTeX cite commands count as citations, ref/eqref commands as cross-references
        lc = p.pop("latex_cmd", [])
        p.setdefault("citation", []).extend(x for x in lc if x.startswith("\\cite"))
        p.setdefault("xref", []).extend(x for x in lc if re.match(r"\\(?:ref|eqref|autoref|cref|Cref|pageref)\b", x))
        p.setdefault("latex_cmd", []).extend(x for x in lc if not re.match(r"\\(?:cite|ref|eqref|autoref|cref|Cref|pageref)", x))
    # I02 citations
    ca, cb = pa.get("citation", []), pb.get("citation", [])
    lost, new = _diff_ms(ca, cb)
    if lost or new:
        add("I02", FAIL, f"citation markers changed: missing {lost}, added {new}")
    elif ca != cb:
        add("I02", WARN, f"citation order changed: {ca} -> {cb}")
    # I03 xrefs
    xa = [_xref_norm(x) for x in pa.get("xref", [])]
    xb = [_xref_norm(x) for x in pb.get("xref", [])]
    lost, new = _diff_ms(xa, xb)
    if lost or new:
        add("I03", FAIL, f"figure/table/equation references changed: missing {lost}, added {new}")
    # I04 math / latex
    ma = pa.get("math", []) + pa.get("latex_cmd", []) + pa.get("url", [])
    mb = pb.get("math", []) + pb.get("latex_cmd", []) + pb.get("url", [])
    lost, new = _diff_ms(ma, mb)
    if lost or new:
        add("I04", FAIL, f"math/LaTeX/URL tokens changed: missing {lost}, added {new}")

    ha, hb = lexical_hits(orig, mask_terms), lexical_hits(rev, mask_terms)
    # I05 hedge strength
    la, lb = _hedge_level(ha), _hedge_level(hb)
    hw = lambda h: (h.get("hedge_weak", []) + h.get("hedge_moderate", []))  # noqa: E731
    wa, wb = len(ha.get("hedge_weak", [])), len(hb.get("hedge_weak", []))
    lost_lv = wb < wa or wb + len(hb.get("hedge_moderate", [])) < wa + len(ha.get("hedge_moderate", []))
    if not translate and la is not None and lb is not None and lb <= la and lost_lv:
        add("I05", FAIL, f"a hedge was removed and not replaced by one of equal or weaker strength: {hw(ha)} -> {hw(hb)}")
    elif translate and la is not None and lb is not None and lb != la:
        add("I05", WARN, f"hedge level changed across languages ({la} -> {lb}): {hw(ha)} -> {hw(hb)}")
    elif la is not None and (lb is None or lb > la):
        add("I05", FAIL, f"hedge removed or weakened (claim strengthened): {hw(ha)} -> {hw(hb) or 'none'}")
    elif lb is not None and (la is None or lb < la):
        add("I05", WARN, f"hedge added or strengthened (claim weakened): {hw(ha) or 'none'} -> {hw(hb)}")
    # I06 boosters
    ba, bb = len(ha.get("booster", [])), len(hb.get("booster", []))
    if bb > ba:
        add("I06", FAIL, f"booster/certainty wording added: {ha.get('booster', [])} -> {hb.get('booster', [])}")
    elif bb < ba:
        add("I06", WARN, f"booster removed (claim softened): {ha.get('booster', [])} -> {hb.get('booster', [])}")
    # I07 approximators
    aa, ab = len(ha.get("approximator", [])), len(hb.get("approximator", []))
    if aa != ab:
        add("I07", FAIL, f"approximator/bound changed (precision of a number): {ha.get('approximator', [])} -> {hb.get('approximator', [])}")
    # I08 significance
    sa, sb = len(ha.get("significance", [])), len(hb.get("significance", []))
    if sa != sb:
        add("I08", FAIL, f"significance wording changed: {ha.get('significance', [])} -> {hb.get('significance', [])}")
    # I09 novelty (priority claims) and promotional intensity
    for cls, label in (("novelty", "novelty/priority claim"), ("promo", "promotional wording")):
        x, y = len(ha.get(cls, [])), len(hb.get(cls, []))
        if y > x:
            add("I09", FAIL, f"{label} added: {ha.get(cls, [])} -> {hb.get(cls, [])}")
        elif y < x:
            add("I09", WARN, f"{label} removed: {ha.get(cls, [])} -> {hb.get(cls, [])}")
    # I10 negation
    ga, gb = len(ha.get("negation", [])), len(hb.get("negation", []))
    if ga != gb:
        add("I10", FAIL, f"negation count changed {ga} -> {gb}: {ha.get('negation', [])} -> {hb.get('negation', [])}")
    # I11 quantifiers
    for q in ("quantifier_universal", "quantifier_majority", "quantifier_partial", "quantifier_exclusive"):
        qa, qb = bool(ha.get(q)), bool(hb.get(q))
        if qa != qb:
            code = "I11u" if q == "quantifier_universal" else "I11"
            add(code, FAIL, f"{q.split('_')[1]} quantifier {'removed' if qa else 'added'}: {ha.get(q, [])} -> {hb.get(q, [])}")
    # I12 causal
    cau = lambda h: [w for w in h.get("causal", []) if w not in INFERENTIAL]  # noqa: E731
    inf = lambda h: [w for w in h.get("causal", []) if w in INFERENTIAL]  # noqa: E731
    if cau(hb) and not cau(ha):
        add("I12", FAIL, f"causal wording introduced{' (original: correlational ' + str(ha.get('correlational')) + ')' if ha.get('correlational') else ''}: {cau(hb)}")
    elif cau(ha) and not cau(hb):
        add("I12", WARN, f"causal wording removed: {cau(ha)} -> {hb.get('correlational', []) or 'none'}")
    if len(inf(hb)) > len(inf(ha)):
        add("I12", WARN, f"inferential connective added: {inf(hb)}")
    if ha.get("correlational") and not hb.get("correlational") and not cau(hb):
        dirs_new = len(hb.get("direction_up", []) + hb.get("direction_down", [])) > len(ha.get("direction_up", []) + ha.get("direction_down", []))
        if dirs_new:
            add("I12", FAIL, f"correlational wording {ha.get('correlational')} replaced by an effect verb {hb.get('direction_up', []) + hb.get('direction_down', [])} (association presented as effect)")
        else:
            add("I12", WARN, f"correlational wording removed: {ha.get('correlational')}")
    # I13 conditions
    ka, kb = len(ha.get("conditional", [])), len(hb.get("conditional", []))
    if kb < ka:
        add("I13", FAIL, f"condition dropped: {ha.get('conditional', [])} -> {hb.get('conditional', []) or 'none'}")
    elif kb > ka:
        add("I13", WARN, f"condition added: {ha.get('conditional', [])} -> {hb.get('conditional', [])}")
    # I14 direction: an antonym swap shows up as fewer words of one polarity and more of the other
    ua_, da_ = len(ha.get("direction_up", [])), len(ha.get("direction_down", []))
    ub_, db_ = len(hb.get("direction_up", [])), len(hb.get("direction_down", []))
    if (ub_ < ua_ and db_ > da_) or (db_ < da_ and ub_ > ua_):
        add("I14", FAIL, f"direction flipped: up {ha.get('direction_up', [])} down {ha.get('direction_down', [])} -> up {hb.get('direction_up', [])} down {hb.get('direction_down', [])}")
    elif (bool(ua_), bool(da_)) != (bool(ub_), bool(db_)):
        add("I14", WARN, f"direction words changed: up {ha.get('direction_up', [])} down {ha.get('direction_down', [])} -> up {hb.get('direction_up', [])} down {hb.get('direction_down', [])}")

    # change records
    records = records or []
    if not translate:
        hs, ratio, ntok = hunks(orig, rev)
        covered = [False] * len(hs)
        for k, r in enumerate(records):
            fr, to = r.get("from", ""), r.get("to", "")
            if not (r.get("reason") or "").strip():
                add("R01", FAIL, f"record {k + 1} has no reason")
            typ = (r.get("type") or "").strip().lower()
            if not typ:
                add("R01", FAIL, f"record {k + 1} has no type")
            elif any(t.strip() not in CHANGE_TYPES for t in re.split(r"[,/+ ]+", typ) if t.strip()):
                add("R05", WARN, f"record {k + 1}: unknown change type '{typ}'")
            fs, ts = _find_all(orig, fr), _find_all(rev, to)
            if fr and not fs:
                add("R01", FAIL, f"record {k + 1}: 'from' text not in the original: {fr!r}")
            if to and not ts:
                add("R01", FAIL, f"record {k + 1}: 'to' text not in the revised sentence: {to!r}")
            if not fr and not to:
                add("R01", FAIL, f"record {k + 1}: empty from and to")
            hit = False
            for i, (a0, a1, b0, b1, _, _) in enumerate(hs):
                ok_a = any(not (e <= a0 or s >= max(a1, a0 + 1)) for s, e in fs) if fr else False
                ok_b = any(not (e <= b0 or s >= max(b1, b0 + 1)) for s, e in ts) if to else False
                if a1 == a0:  # insertion
                    ok_a = ok_a or any(s <= a0 <= e for s, e in fs)
                if b1 == b0:  # deletion
                    ok_b = ok_b or any(s <= b0 <= e for s, e in ts)
                if ok_a or ok_b:
                    covered[i] = True
                    hit = True
            if not hit and (fs or ts) and hs:
                add("R05", WARN, f"record {k + 1} does not overlap any change: {fr!r} -> {to!r}")
        undoc = [(h[4], h[5]) for h, c in zip(hs, covered) if not c]
        if undoc:
            add("R02", FAIL, "changes without a record: " + "; ".join(f"{a!r}->{b!r}" for a, b in undoc[:6]) + (" ..." if len(undoc) > 6 else ""))
        if not hs and records:
            add("R05", WARN, "records given but the sentence is unchanged")
        frac = 1 - ratio
        types = {t.strip() for r in records for t in re.split(r"[,/+ ]+", (r.get("type") or "").lower()) if t.strip()}
        if hs and frac > 0.55 and ntok > 8 and not (types & HEAVY_OK):
            add("R03", WARN, f"heavy rewrite ({frac:.0%} of tokens changed) without a restructure/sentence-split type")
    # residual style issues
    lg = lang or ("zh" if re.search(f"[{CJK}]", rev) and len(re.findall(f"[{CJK}]", rev)) > len(re.findall('[A-Za-z]', rev)) / 2 else "en")
    for h in lint(rev, lg, genre, residual_only=True):
        add("R04", WARN, f"{h['rule']} {h['message']}: \"{h['match']}\"")

    accept = accept or {}
    for x in f:
        reason = accept.get(x["code"]) or (accept.get("I11") if x["code"] == "I11u" else None)
        if reason and x["severity"] in (FAIL, WARN):
            x["accepted"] = reason
            x["severity_original"] = x["severity"]
            x["severity"] = "accepted"
    return f


def verdict(findings):
    sev = {x["severity"] for x in findings}
    return FAIL if FAIL in sev else WARN if WARN in sev else "pass"


# ---------------------------------------------------------------- document level

US_UK = [("analyze", "analyse"), ("color", "colour"), ("behavior", "behaviour"), ("center", "centre"), ("fiber", "fibre"),
         ("modeling", "modelling"), ("labeled", "labelled"), ("optimize", "optimise"), ("characterize", "characterise"),
         ("normalize", "normalise"), ("utilize", "utilise"), ("minimize", "minimise"), ("organization", "organisation"),
         ("favorable", "favourable"), ("aluminum", "aluminium"), ("sulfur", "sulphur"), ("gray", "grey"), ("tumor", "tumour"),
         ("program", "programme"), ("catalog", "catalogue"), ("defense", "defence"), ("estrogen", "oestrogen")]
ABBR_COMMON = {"DNA", "RNA", "PCR", "USA", "UK", "EU", "UV", "IR", "NMR", "AI", "CPU", "GPU", "PDF", "ID", "OK", "II", "III", "IV",
               "SI", "ISO", "pH", "HIV", "COVID", "SARS", "WHO", "NASA", "MATLAB", "API", "URL", "HTML", "XML", "JSON", "CSV",
               "LaTeX", "RGB", "CMOS", "LED", "AC", "DC", "TM", "CO", "CO2", "NO", "OH", "ATP", "mRNA", "SD", "SEM", "TEM",
               "XRD", "XPS", "MS", "HPLC", "ANOVA", "CI", "OR", "HR", "BMI", "ICU", "MRI", "CT", "PET", "FFT", "IEEE", "NSFC",
               "ACS", "APS", "IOP", "RSC", "AIP"}


def doc_checks(rev_text, terms, mode="polish", pairs=None, segs=None):
    """Whole-document checks on the revised text. pairs = [(sid, orig, rev)] for term alignment in translation."""
    out = []
    plain = re.sub(r"\$[^$]*\$|\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{[^{}]*\})?", " ", rev_text)
    # D01 termbase variants
    for e in terms:
        for v in e.get("variants", []):
            rx = term_regex(v)
            if rx is None:
                continue
            hits = [m.group(0) for m in rx.finditer(plain)]
            if hits:
                pr = term_regex(e["preferred"])
                # do not count a variant that is only a substring of the preferred form at the same place
                if pr and all(any(m2.start() <= m.start() < m2.end() for m2 in pr.finditer(plain)) for m in rx.finditer(plain)):
                    continue
                sids = []
                if segs:
                    for sg in segs:
                        if rx.search(sg.get("revised", sg["text"])):
                            sids.append(sg["sid"])
                out.append({"code": "D01", "severity": FAIL if e.get("source") not in ("agent",) else WARN,
                            "detail": f"variant '{v}' used {len(hits)}x; termbase prefers '{e['preferred']}'", "sids": sids[:20],
                            "term": e["preferred"]})
    # D02 term alignment for translation
    if mode.startswith("translate") and pairs:
        for e in terms:
            src, tgt = e.get("zh"), e.get("en") or e.get("preferred")
            if not src or not tgt or not re.search(f"[{CJK}]", src):
                continue
            rs, rt = term_regex(src), term_regex(tgt)
            ra = term_regex(e["abbr"]) if e.get("abbr") else None
            for sid, o, r in pairs:
                if rs and rs.search(o) and not (rt and rt.search(r)) and not (ra and ra.search(r)):
                    out.append({"code": "D02", "severity": WARN, "detail": f"source term '{src}' present but '{tgt}' not in the translation", "sids": [sid], "term": tgt})
    # D03 abbreviations
    defs = abbreviation_definitions(plain)
    first_def = {}
    longs = {}
    for ab, lf, pos in defs:
        longs.setdefault(ab, set()).add(_norm_term(lf))
        if ab in first_def:
            out.append({"code": "D03", "severity": WARN, "detail": f"abbreviation {ab} defined again (first definition at char {first_def[ab]})", "term": ab})
        else:
            first_def[ab] = pos
    for ab, ls in longs.items():
        if len(ls) > 1:
            out.append({"code": "D03", "severity": WARN, "detail": f"abbreviation {ab} expanded in different ways: {sorted(ls)}", "term": ab})
    for e in terms:
        if e.get("abbr") and e["abbr"] not in first_def:
            first_use = re.search(r"(?<![\w-])" + re.escape(e["abbr"]) + r"(?![\w-])", plain)
            if first_use:
                out.append({"code": "D03", "severity": WARN, "detail": f"termbase abbreviation {e['abbr']} used but never defined as '{e['preferred']} ({e['abbr']})'", "term": e["abbr"]})
    for ab, pos in first_def.items():
        m = re.search(r"(?<![\w-])" + re.escape(ab) + r"(?![\w-])", plain)
        if m and m.start() < pos - 2:
            ctx = plain[max(0, m.start() - 30):m.end() + 10].replace("\n", " ")
            out.append({"code": "D03", "severity": WARN, "detail": f"{ab} used before its definition: '...{ctx}...'", "term": ab})
    used = Counter(re.findall(r"(?<![\w-])([A-Z][A-Z0-9]{1,7}s?)(?![\w-])", plain))
    undefined = sorted(a for a in used if a.rstrip("s") not in first_def and a not in first_def and a.rstrip("s") not in ABBR_COMMON
                       and a not in ABBR_COMMON and not any(a == e.get("abbr") for e in terms) and not re.fullmatch(r"[A-Z]", a) and not re.fullmatch(r"[IVX]+", a))
    if undefined:
        out.append({"code": "D03", "severity": INFO, "detail": f"abbreviations without a definition in this text (may be defined elsewhere / standard): {undefined[:25]}"})
    # D04 hyphen/space/case drift
    words = re.findall(r"[A-Za-z][A-Za-z0-9]*(?:[- ][A-Za-z][A-Za-z0-9]*){1,2}", plain)
    hy = {}
    for m in re.finditer(r"(?<![\w-])([A-Za-z][a-z0-9]+)-([A-Za-z][a-z0-9]+)(?![\w-])", plain):
        hy.setdefault((m.group(1).lower(), m.group(2).lower()), set()).add("hyphen")
    for (a, b) in list(hy):
        if re.search(r"(?<![\w-])" + a + r" " + b + r"(?![\w-])", plain, flags=re.I):
            out.append({"code": "D04", "severity": WARN, "detail": f"'{a}-{b}' and '{a} {b}' both used", "term": f"{a}-{b}"})
        if re.search(r"(?<![\w-])" + a + b + r"(?![\w-])", plain, flags=re.I):
            out.append({"code": "D04", "severity": WARN, "detail": f"'{a}-{b}' and '{a}{b}' both used", "term": f"{a}-{b}"})
    del words
    for e in terms:
        rx = term_regex(e["preferred"])
        if rx and re.search(r"[a-z]", e["preferred"]):
            forms = Counter(m.group(0).rstrip("s") for m in rx.finditer(plain)
                            if not re.search(r"(?:^|[.!?]\s+|\n)$", plain[max(0, m.start() - 3):m.start()]))
            if len(forms) > 1:
                out.append({"code": "D04", "severity": WARN, "detail": f"term '{e['preferred']}' written in several forms: {dict(forms)}", "term": e["preferred"]})
    # D05 US/UK
    for us, uk in US_UK:
        a = len(re.findall(r"(?<![a-z])" + us, plain, flags=re.I))
        b = len(re.findall(r"(?<![a-z])" + uk, plain, flags=re.I))
        if a and b:
            out.append({"code": "D05", "severity": WARN, "detail": f"mixed spelling: {us}* x{a} and {uk}* x{b}"})
    return out


# ---------------------------------------------------------------- standalone alignment mode

def align(a_segs, b_segs):
    """Pair sentences of two versions (difflib over sentence texts, then greedy within replace blocks)."""
    A, B = [s["text"] for s in a_segs], [s["text"] for s in b_segs]
    sm = difflib.SequenceMatcher(None, A, B, autojunk=False)
    pairs = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            pairs += [(a_segs[i], b_segs[j1 + k]) for k, i in enumerate(range(i1, i2))]
        elif op == "replace":
            used = set()
            for i in range(i1, i2):
                best, bj = 0, None
                for j in range(j1, j2):
                    if j in used:
                        continue
                    r = difflib.SequenceMatcher(None, A[i], B[j], autojunk=False).ratio()
                    if r > best:
                        best, bj = r, j
                if bj is not None and best > 0.2:
                    used.add(bj)
                    pairs.append((a_segs[i], b_segs[bj]))
                else:
                    pairs.append((a_segs[i], None))
            pairs += [(None, b_segs[j]) for j in range(j1, j2) if j not in used]
        elif op == "delete":
            pairs += [(a_segs[i], None) for i in range(i1, i2)]
        else:
            pairs += [(None, b_segs[j]) for j in range(j1, j2)]
    return pairs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--orig", required=True)
    ap.add_argument("--rev", required=True)
    ap.add_argument("--mode", default="polish")
    ap.add_argument("--termbase")
    ap.add_argument("--genre")
    ap.add_argument("--json")
    a = ap.parse_args()
    ta, fa, _ = read_any(a.orig)
    tb, fb, _ = read_any(a.rev)
    sa, sb = segment(ta, fa), segment(tb, fb)
    terms = load_termbase(a.termbase) if a.termbase else []
    report = {"pairs": [], "doc": [], "termbase_conflicts": termbase_conflicts(terms)}
    for x, y in align(sa, sb):
        if x is None or y is None:
            report["pairs"].append({"orig_sid": x and x["sid"], "rev_sid": y and y["sid"], "orig": x and x["text"], "rev": y and y["text"],
                                    "findings": [{"code": "A01", "severity": WARN, "detail": "sentence added" if x is None else "sentence deleted (or merged)"}]})
            continue
        if x["text"] == y["text"]:
            continue
        fd = [z for z in check_pair(x["text"], y["text"], a.mode, [], None, a.genre)
              if z["code"] not in ("R02", "R03")]
        report["pairs"].append({"orig_sid": x["sid"], "rev_sid": y["sid"], "orig": x["text"], "rev": y["text"], "findings": fd})
    report["doc"] = doc_checks(tb, terms, a.mode)
    sev = Counter(f["severity"] for p in report["pairs"] for f in p["findings"])
    sev.update(f["severity"] for f in report["doc"])
    report["summary"] = {"changed_pairs": len(report["pairs"]), "severity": dict(sev),
                         "codes": dict(Counter(f["code"] for p in report["pairs"] for f in p["findings"] if f["severity"] in (FAIL, WARN)))}
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=1)
    for p in report["pairs"]:
        bad = [f for f in p["findings"] if f["severity"] in (FAIL, WARN)]
        if bad:
            print(f"[{p['orig_sid']}] {verdict(bad)}")
            for f in bad:
                print(f"   {f['code']} {f['severity']}: {f['detail']}")
    for d in report["doc"]:
        print(f"[doc] {d['code']} {d['severity']}: {d['detail']}")
    print(json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
