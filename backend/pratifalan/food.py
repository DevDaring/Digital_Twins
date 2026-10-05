"""Indian food composition table lookups (nutrition never comes from an LLM).

Two kinds of lookup:

* ``match(name)``: fuzzy match of ONE dish name (meal-photo labels, food search box).
* ``find_in_text(text)``: deterministic extraction of every dish named in a chat
  message, in English, Hindi, Bengali or Kannada (native script or romanised). It uses
  exact phrase keys (longest phrase first), light inflection stripping for the Indic
  scripts (रोटियाँ -> रोटी, ভাতের -> ভাত, ಮುದ್ದೆಯನ್ನು -> ಮುದ್ದೆ) and a high-cutoff
  fuzzy fallback for romanised typos only. Words that are also common non-food words
  ("am", "dose", "sugar" as in blood sugar, ...) only count when a quantity precedes them.
"""

from __future__ import annotations

import difflib
import json
import re
import unicodedata
from functools import lru_cache

import pandas as pd

from pratifalan.config import FOOD_DIR

LANG_COL = {"en-IN": "name_en", "hi-IN": "name_hi", "bn-IN": "name_bn", "kn-IN": "name_kn"}
NAME_COLS = ("name_en", "name_hi", "name_bn", "name_kn")

# Colloquial / everyday native-script words people actually say in chat. The table's
# native names are formal ("चावल (पका हुआ)"); these map the plain word to the most
# common everyday dish. Kept small and conservative on purpose.
EXTRA_KEYS: dict[str, tuple[str, ...]] = {
    "white_rice_katori": ("चावल", "भात", "ভাত", "ಅನ್ನ", "ಬಿಳಿ ಅನ್ನ"),
    "roti_piece": ("रोटी", "चपाती", "फुलका", "রুটি", "চাপাটি", "ರೊಟ್ಟಿ", "ಚಪಾತಿ"),
    "dal_toor_katori": ("दाल", "अरहर दाल", "तूर दाल", "ಬೇಳೆ ಸಾರು", "ತೊಗರಿ ಬೇಳೆ", "ದಾಲ್"),
    "dal_masoor_katori": ("ডাল", "মুসুর ডাল", "মসুর ডাল"),
    "dal_moong_katori": ("मूंग दाल", "মুগ ডাল", "ಹೆಸರು ಬೇಳೆ"),
    "paratha_piece": ("पराठा", "परांठा", "পরোটা", "ಪರೋಟ", "ಪರೋಟಾ"),
    "puri_piece": ("पूरी", "पूड़ी", "পুরি", "ಪೂರಿ"),
    "idli_piece": ("इडली", "ইডলি", "ಇಡ್ಲಿ"),
    "dosa_piece": ("डोसा", "দোসা", "ದೋಸೆ", "ದೋಸಾ"),
    "khichdi_plate": ("खिचड़ी", "খিচুড়ি", "ಕಿಚಡಿ"),
    "mixed_veg_katori": ("सब्ज़ी", "सब्जी", "তরকারি", "সবজি", "ಪಲ್ಯ"),
    "curd_katori": ("दही", "দই", "টক দই", "ಮೊಸರು"),
    "masala_chai_sugar_cup": ("चाय", "চা", "ಟೀ", "ಚಹಾ"),
    "filter_coffee_cup": ("कॉफ़ी", "কফি", "ಕಾಫಿ"),
    "milk_glass": ("दूध", "দুধ", "ಹಾಲು"),
    "banana_piece": ("केला", "কলা", "ಬಾಳೆಹಣ್ಣು", "ಬಾಳೆ ಹಣ್ಣು"),
    "mango_katori": ("आम", "আম", "ಮಾವಿನ ಹಣ್ಣು", "ಮಾವು"),
    "samosa_piece": ("समोसा", "শিঙাড়া", "সিঙাড়া", "ಸಮೋಸ", "ಸಮೋಸಾ"),
    "poha_plate": ("पोहा", "ಅವಲಕ್ಕಿ"),
    "upma_katori": ("उपमा", "ಉಪ್ಪಿಟ್ಟು", "ಉಪ್ಮಾ"),
    "ragi_mudde_piece": ("ಮುದ್ದೆ", "ರಾಗಿ ಮುದ್ದೆ", "ರಾಗಿಮುದ್ದೆ"),
    "rasam_katori": ("ಸಾರು", "रसम", "রসম"),
    "sambar_katori": ("ಸಾಂಬಾರ್", "ಸಾಂಬಾರು", "सांभर", "सांबर"),
    "macher_jhol_katori": ("মাছের ঝোল", "মাছ"),
    "luchi_piece": ("লুচি",),
    "muri_cup": ("মুড়ি", "मुरमुरे", "ಮಂಡಕ್ಕಿ"),
    "boiled_egg_piece": ("अंडा", "ডিম", "ಮೊಟ್ಟೆ"),
    "sugar_tsp": ("चीनी", "চিনি", "ಸಕ್ಕರೆ"),
}

# Keys that are also everyday non-food words (or "sugar" meaning blood sugar): they
# only count as food when a quantity or unit word comes right before them.
NEEDS_QTY = {
    "am", "dose", "dim", "nan", "cha", "mor", "sugar", "anna", "kola", "lau", "pori", "sev", "ata", "aata",
    "sakkare", "chini", "cheeni", "matha", "ghol", "pepe", "chura", "chida",
    "चीनी", "চিনি", "ಸಕ್ಕರೆ",
}
# Never matched on their own (fuzzy or exact), whatever the table says.
STOP = {
    "and", "now", "khana", "khaana", "khabo", "khele", "tindre", "eat", "ate", "eating", "meal", "food", "dinner",
    "lunch", "breakfast", "snack", "today", "tonight", "with", "without", "then", "what", "will", "happen",
    "after", "before", "plate", "piece", "bowl", "glass", "cup", "katori", "half", "full", "more", "less",
    "खाना", "खाऊँ", "खाऊं", "और", "अभी", "খাবার", "আর", "এখন", "ಊಟ", "ಮತ್ತು", "ಈಗ",
}

QTY_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "half": 0.5, "a": 1, "an": 1, "single": 1,
    "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पाँच": 5, "पांच": 5, "आधा": 0.5, "आधी": 0.5, "डेढ़": 1.5, "ढाई": 2.5,
    "এক": 1, "একটা": 1, "একটি": 1, "দুই": 2, "দুটো": 2, "দুটি": 2, "তিন": 3, "তিনটে": 3, "তিনটি": 3, "চার": 4,
    "চারটে": 4, "পাঁচ": 5, "আধা": 0.5, "আধ": 0.5, "দেড়": 1.5,
    "ಒಂದು": 1, "ಎರಡು": 2, "ಮೂರು": 3, "ನಾಲ್ಕು": 4, "ಐದು": 5, "ಅರ್ಧ": 0.5, "ಒಂದೂವರೆ": 1.5,
}
HALF_WORDS = {"half", "आधा", "आधी", "আধা", "আধ", "ಅರ್ಧ"}
UNIT_WORDS = {
    "katori", "katoris", "bowl", "bowls", "plate", "plates", "piece", "pieces", "cup", "cups", "glass", "glasses",
    "tsp", "tbsp", "spoon", "spoons", "serving", "servings", "slice", "slices", "handful",
    "कटोरी", "प्लेट", "कप", "गिलास", "चम्मच", "टुकड़ा", "টুকরো", "বাটি", "প্লেট", "কাপ", "গ্লাস", "চামচ",
    "ಬಟ್ಟಲು", "ತಟ್ಟೆ", "ಕಪ್", "ಲೋಟ", "ಚಮಚ",
}

_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯०१२३४५६७८९೦೧೨೩೪೫೬೭೮೯", "012345678901234567890123456789")

# Inflection rules per script: (suffix, replacement). Tried on the LAST token of a
# phrase only when the plain phrase is not a key; the result must be an exact key.
_INFLECT = (
    # Hindi (Devanagari) plurals / oblique case
    ("ियां", "ी"), ("ियों", "ी"), ("ों", ""), ("ों", "ा"), ("ें", ""), ("े", "ा"), ("े", ""),
    # Bengali classifiers and case endings
    ("গুলো", ""), ("গুলি", ""), ("টুকু", ""), ("টা", ""), ("টি", ""), ("ের", ""), ("র", ""), ("কে", ""),
    ("ে", ""), ("ও", ""),
    # Kannada case endings and plural
    ("ಗಳನ್ನು", ""), ("ಗಳು", ""), ("ವನ್ನು", ""), ("ಯನ್ನು", ""), ("ನ್ನು", "ು"), ("ಕ್ಕೆ", ""), ("ದ", ""),
    ("ಯ", ""), ("ವೂ", ""), ("ಯೂ", ""),
    # English plurals
    ("es", ""), ("s", ""),
)


@lru_cache
def table() -> pd.DataFrame:
    df = pd.read_csv(FOOD_DIR / "indian_foods.csv")
    df["aliases"] = df["aliases"].fillna("")
    return df


@lru_cache
def _by_id() -> dict[str, pd.Series]:
    return {r["id"]: r for _, r in table().iterrows()}


@lru_cache
def swaps() -> list[dict]:
    return json.loads((FOOD_DIR / "swaps.json").read_text(encoding="utf-8"))


SWAP_LABEL_COL = {"en-IN": "label_en", "hi-IN": "label_hi", "bn-IN": "label_bn", "kn-IN": "label_kn"}


def swaps_localised(lang: str = "en-IN") -> list[dict]:
    """Contract shape: [{from, to, from_qty, to_qty, label (in ``lang``, English fallback), label_en}]."""
    col = SWAP_LABEL_COL.get(lang, SWAP_LABEL_COL.get(f"{lang}-IN", "label_en"))
    return [{"from": s["from"], "to": s["to"], "from_qty": s.get("from_qty", 1), "to_qty": s.get("to_qty", 1),
             "label": s.get(col) or s["label_en"], "label_en": s["label_en"]} for s in swaps()]


def _norm(s: str) -> str:
    """Lowercase, unify digits / nukta / chandrabindu / joiners, drop punctuation."""
    t = unicodedata.normalize("NFC", str(s)).lower().translate(_DIGITS)
    t = unicodedata.normalize("NFD", t)
    t = t.replace("़", "").replace("়", "").replace("಼", "")  # nukta
    t = t.replace("ँ", "ं")  # chandrabindu -> anusvara (रोटियाँ == रोटियां)
    t = t.replace("‌", "").replace("‍", "")
    t = unicodedata.normalize("NFC", t)
    t = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", t)
    t = re.sub(r"[^a-z0-9.ऀ-෿ ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _name_variants(name: str) -> tuple[list[str], list[str]]:
    """(full names, reduced names): 'Roti / chapati (no ghee)' -> full [...], reduced ['roti', 'chapati']."""
    if not isinstance(name, str) or not name.strip():
        return [], []
    full = [name]
    base = re.sub(r"\([^)]*\)", " ", name)
    parts = [p for p in re.split(r"[/,]", base) if p.strip()]
    reduced = [base, *parts] if base.strip() != name.strip() or len(parts) > 1 else []
    return full, reduced


@lru_cache
def _keys() -> dict[str, str]:
    """Exact phrase key -> food id. Priority: full names > aliases > colloquial > reduced names."""
    ranked: dict[str, tuple[int, int, str]] = {}

    def put(key: str, fid: str, prio: int, order: int) -> None:
        k = _norm(key)
        if not k or k in STOP:
            return
        cur = ranked.get(k)
        if cur is None or (prio, order) < cur[:2]:
            ranked[k] = (prio, order, fid)

    t = table()
    for order, (_, r) in enumerate(t.iterrows()):
        fid = r["id"]
        for col in NAME_COLS:
            full, reduced = _name_variants(r[col])
            for k in full:
                put(k, fid, 0, order)
            for k in reduced:
                put(k, fid, 3, order)
        for a in r["aliases"].split(";"):
            if a.strip():
                put(a, fid, 1, order)
    ids = set(t["id"])
    for fid, words in EXTRA_KEYS.items():
        if fid in ids:
            for w in words:
                put(w, fid, 2, 0)
    return {k: v[2] for k, v in ranked.items()}


@lru_cache
def _latin_singles() -> list[str]:
    return [k for k in _keys() if " " not in k and re.fullmatch(r"[a-z]{5,}", k) and k not in NEEDS_QTY]


@lru_cache
def _index() -> list[tuple[str, str]]:
    return list(_keys().items())


def food_json(row: pd.Series, lang: str = "en-IN") -> dict:
    name = row.get(LANG_COL.get(lang, "name_en"), row["name_en"])
    return {
        "id": row["id"], "name": name if isinstance(name, str) and name else row["name_en"], "name_en": row["name_en"],
        "unit": row["unit"], "unit_label": row["unit_label_en"], "grams_per_unit": float(row["grams_per_unit"]),
        "carbs_g": float(row["carbs_g"]), "fibre_g": float(row["fibre_g"]), "protein_g": float(row["protein_g"]),
        "fat_g": float(row["fat_g"]), "kcal": float(row["kcal"]), "cuisine": row["cuisine"],
        "category": row["category"], "source": row["source"],
    }


def spoken_name(name: str) -> str:
    """Short, TTS-friendly dish name: no brackets, no slashes, no trailing portion note.

    'Roti / chapati (no ghee)' -> 'Roti'; 'Toor / arhar dal (dal tadka)' -> 'Toor dal';
    'Pakora / pakoda (onion), 4 pieces' -> 'Pakora'; 'अरहर / तूर दाल' -> 'अरहर दाल'."""
    if not isinstance(name, str):
        return ""
    base = re.sub(r"\s*\([^)]*\)", "", name).split(",")[0].strip()
    parts = [p.strip() for p in base.split("/") if p.strip()]
    if not parts:
        return name.strip()
    first, last = parts[0], parts[-1]
    fw, lw = first.split(), last.split()
    if len(parts) > 1 and len(fw) == 1 and len(lw) > 1:
        return " ".join([fw[0], *lw[1:]])  # shared head noun: "Toor / arhar dal" -> "Toor dal"
    return first


def get(food_id: str) -> pd.Series | None:
    return _by_id().get(food_id)


def match(name: str, n: int = 5, cutoff: float = 0.6) -> list[tuple[str, float]]:
    """Fuzzy match ONE free-text dish name to table ids (best first, with a score)."""
    q = _norm(name)
    if not q:
        return []
    keys = _keys()
    if q in keys:
        exact = keys[q]
        rest = [(f, s) for f, s in _fuzzy(q, n + 1) if f != exact]
        return [(exact, 1.0), *[(f, s) for f, s in rest if s >= cutoff]][:n]
    return [(fid, s) for fid, s in _fuzzy(q, n) if s >= cutoff]


# Words that describe a preparation rather than the dish itself: 'paneer curry' is about paneer.
GENERIC_WORDS = {"curry", "sabzi", "sabji", "subzi", "masala", "gravy", "dish", "fry", "fried", "bhaja", "bhaji",
                 "jhol", "with", "and", "of", "the", "a", "plain", "homemade", "style", "indian", "tarkari",
                 "torkari", "palya", "poriyal", "sukhi", "dry", "item", "side"}


def _fuzzy(q: str, n: int) -> list[tuple[str, float]]:
    scores: dict[str, float] = {}
    qs = q.split()
    core = [w for w in qs if w not in GENERIC_WORDS and len(w) >= 3]
    for key, fid in _index():
        ks = key.split()
        if q == key:
            s = 1.0
        elif q in ks or key in qs:
            s = 0.85
        elif len(q) > 3 and (q in key or key in q):
            s = 0.8
        else:
            s = difflib.SequenceMatcher(None, q, key).ratio()
        if core and len(qs) > 1 and s < 0.95 and all(w in ks for w in core):
            # every distinctive word of the query is a word of this dish name: 'paneer curry' ->
            # 'matar paneer' ranks above 'chingri malaikari'; a matching preparation word adds a little
            s = max(s, 0.86 + 0.02 * sum(1 for w in qs if w in GENERIC_WORDS and w in ks))
        if s > scores.get(fid, 0):
            scores[fid] = s
    prep = set(qs) & GENERIC_WORDS
    if prep:
        for fid, sc in list(scores.items()):
            if 0.8 <= sc < 1.0:
                scores[fid] = sc + 0.01 * _prep_fit(fid, prep)
    return sorted(scores.items(), key=lambda kv: -kv[1])[:n]


CURRY_WORDS = {"curry", "sabzi", "sabji", "subzi", "masala", "gravy", "jhol", "tarkari", "torkari", "palya", "poriyal"}
FRY_WORDS = {"fry", "fried", "bhaja", "bhaji"}


def _prep_fit(fid: str, prep: set[str]) -> int:
    """Tie-break by preparation: 'paneer curry' prefers curries, 'aloo bhaja' prefers fried sides."""
    r = get(fid)
    if r is None:
        return 0
    text = f"{r['name_en']} {r['aliases']}".lower()
    fit = 0
    if prep & CURRY_WORDS and r["category"] in ("curry", "veg", "dal", "nonveg"):
        fit += 1
    if prep & FRY_WORDS and re.search(r"\b(fry|fried|bhaja|bhaji|fritter)\b", text):
        fit += 2
    return fit


def search(q: str, lang: str = "en-IN", n: int = 12) -> list[dict]:
    t = table()
    if not q.strip():
        return [food_json(r, lang) for _, r in t.head(n).iterrows()]
    out: list[dict] = []
    for fid, _ in match(q, n=n, cutoff=0.45):
        r = get(fid)
        if r is not None:
            out.append(food_json(r, lang))
    return out


# ----------------------------------------------------------------------------- free text
def tokens(text: str) -> list[str]:
    return _norm(text.replace("-", " ")).split()


def _inflected(tok: str) -> list[str]:
    """Candidate base forms; the stem must keep >= 3 code points (চার "four" must not become চা "tea")."""
    out: list[str] = []
    if tok in QTY_WORDS or tok in UNIT_WORDS:
        return out
    for suf, rep in _INFLECT:
        if tok.endswith(suf) and len(tok) - len(suf) >= 3:
            out.append(tok[: len(tok) - len(suf)] + rep)
    return out


def _lookup(words: list[str]) -> tuple[str, str] | None:
    """(food id, the key that matched) for an exact phrase, allowing one inflected last word."""
    keys = _keys()
    phrase = " ".join(words)
    if phrase in keys:
        return keys[phrase], phrase
    joined = "".join(words)
    # "ರಾಗಿ ಮುದ್ದೆ" vs "ರಾಗಿಮುದ್ದೆ": native script only (romanised "and a" must not become "anda")
    if len(words) > 1 and joined in keys and not re.search(r"[a-z]", joined) and min(map(len, words)) >= 2:
        return keys[joined], joined
    for v in _inflected(words[-1]):
        p = " ".join([*words[:-1], v])
        if p in keys and p not in STOP:
            return keys[p], p
    return None


def _qty_before(toks: list[str], i: int) -> tuple[float, bool, bool]:
    """(quantity, explicit?, from a 'half' word?) for a dish starting at token i."""
    j = i - 1
    if j >= 0 and toks[j] in UNIT_WORDS:
        j -= 1
    if j >= 0:
        w = toks[j]
        if re.fullmatch(r"\d+(\.\d+)?", w):
            return float(w), True, False
        if w in QTY_WORDS:
            return float(QTY_WORDS[w]), True, w in HALF_WORDS
    return 1.0, i - 1 >= 0 and toks[i - 1] in UNIT_WORDS, False


def find_in_text(text: str, max_n: int = 6) -> list[dict]:
    """Every dish named in ``text`` -> [{food_id, units, matched, half_word, explicit}] in order of mention."""
    toks = tokens(text)
    found: list[dict] = []
    seen: set[str] = set()
    i = 0
    while i < len(toks):
        hit = None
        for n in range(min(max_n, len(toks) - i), 0, -1):
            words = toks[i:i + n]
            if n == 1 and (words[0] in STOP or words[0] in QTY_WORDS or words[0] in UNIT_WORDS
                           or re.fullmatch(r"[\d.]+", words[0])):
                continue
            res = _lookup(words)
            if res is None and n == 1:
                res = _fuzzy_token(words[0])
            if res is not None:
                hit = (res[0], res[1], n)
                break
        if hit is None:
            i += 1
            continue
        fid, key, n = hit
        qty, explicit, half = _qty_before(toks, i)
        phrase = " ".join(toks[i:i + n])
        if key in NEEDS_QTY and not explicit:
            i += 1
            continue
        if fid not in seen:
            seen.add(fid)
            found.append({"food_id": fid, "units": qty, "matched": phrase, "half_word": half, "explicit": explicit})
        i += n
    return found


def _fuzzy_token(tok: str) -> tuple[str, str] | None:
    if not re.fullmatch(r"[a-z]{5,}", tok) or tok in STOP:
        return None
    m = difflib.get_close_matches(tok, _latin_singles(), n=1, cutoff=0.88)
    return (_keys()[m[0]], m[0]) if m else None


def macros(items: list[dict]) -> dict:
    """Sum macros for [{food_id, units}]."""
    tot = {"carbs": 0.0, "fibre": 0.0, "protein": 0.0, "fat": 0.0, "kcal": 0.0}
    for it in items:
        r = get(it["food_id"])
        if r is None:
            continue
        u = float(it.get("units", 1))
        tot["carbs"] += u * r["carbs_g"]
        tot["fibre"] += u * r["fibre_g"]
        tot["protein"] += u * r["protein_g"]
        tot["fat"] += u * r["fat_g"]
        tot["kcal"] += u * r["kcal"]
    return {k: round(v, 1) for k, v in tot.items()}
