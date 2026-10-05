"""Multilingual dish extraction from chat text (food.find_in_text / orchestrator.parse_foods)."""

from __future__ import annotations

import pytest

from pratifalan import food
from pratifalan.agent.orchestrator import parse_foods

RICE, ROTI, DAL = "white_rice_katori", "roti_piece", "dal_toor_katori"

# (text, expected [(food_id, units), ...] in order of mention)
CASES: list[tuple[str, list[tuple[str, float]]]] = [
    # --- English / romanised
    ("if i eat 2 roti and dal now", [(ROTI, 2), (DAL, 1)]),
    ("What happens if I have rice and dal for dinner?", [(RICE, 1), (DAL, 1)]),
    ("3 idlis and sambar", [("idli_piece", 3), ("sambar_katori", 1)]),
    ("chicken biryani and a glass of lassi", [("chicken_biryani_plate", 1), ("lassi_sweet_glass", 1)]),
    ("two chapatis with palak paneer", [(ROTI, 2), ("palak_paneer_katori", 1)]),
    ("ragi mudde with saaru", [("ragi_mudde_piece", 1), ("rasam_katori", 1)]),
    ("half plate rice", [(RICE, 0.5)]),
    ("2 tsp sugar in my chai", [("sugar_tsp", 2), ("masala_chai_sugar_cup", 1)]),
    ("bhat, macher jhol and begun bhaja", [(RICE, 1), ("macher_jhol_katori", 1), ("begun_bhaja_piece", 1)]),
    ("I am eating rice now", [(RICE, 1)]),                       # "am" is not mango
    ("my sugar is 140, can I eat a banana?", [("banana_piece", 1)]),  # blood "sugar" is not table sugar
    ("2 samosas and masala chai", [("samosa_piece", 2), ("masala_chai_sugar_cup", 1)]),
    ("chapatti and aloo sabzi", [(ROTI, 1), ("aloo_sabzi_katori", 1)]),      # spelling variant
    # --- Hindi
    ("अगर मैं अभी चावल और दाल खाऊँ तो क्या होगा?", [(RICE, 1), (DAL, 1)]),
    ("दो रोटियाँ और सब्ज़ी", [(ROTI, 2), ("mixed_veg_katori", 1)]),
    ("दो रोटियां और सब्जी", [(ROTI, 2), ("mixed_veg_katori", 1)]),          # anusvara / no nukta
    ("तीन पराठे और दही", [("paratha_piece", 3), ("curd_katori", 1)]),
    ("मैं खिचड़ी खाऊँगा", [("khichdi_plate", 1)]),
    ("एक केला और चाय", [("banana_piece", 1), ("masala_chai_sugar_cup", 1)]),
    ("राजमा चावल खाने से क्या होगा", [("rajma_katori", 1), (RICE, 1)]),
    # --- Bengali
    ("ভাত আর ডাল খেলে কী হবে?", [(RICE, 1), ("dal_masoor_katori", 1)]),
    ("দুটো রুটি খাব", [(ROTI, 2)]),
    ("ভাতের সঙ্গে মাছের ঝোল", [(RICE, 1), ("macher_jhol_katori", 1)]),
    ("একটা রসগোল্লা খেলে সুগার কত হবে", [("rasgulla_piece", 1)]),
    ("লুচি আর আলুর দম", [("luchi_piece", 1)]),
    ("চার টুকরো রুটি", [(ROTI, 4)]),
    # --- Kannada
    ("ನಾನು ಈಗ ರಾಗಿ ಮುದ್ದೆ ಮತ್ತು ಸಾರು ತಿಂದರೆ ಏನಾಗುತ್ತದೆ?", [("ragi_mudde_piece", 1), ("rasam_katori", 1)]),
    ("ಎರಡು ರೊಟ್ಟಿಗಳು ಮತ್ತು ಅನ್ನವನ್ನು ತಿಂದರೆ", [(ROTI, 2), (RICE, 1)]),
    ("ಅನ್ನ ಸಾಂಬಾರ್", [(RICE, 1), ("sambar_katori", 1)]),
    ("ಮೂರು ಇಡ್ಲಿ ಮತ್ತು ಕಾಯಿ ಚಟ್ನಿ", [("idli_piece", 3), ("coconut_chutney_tbsp", 1)]),
    ("ಮುದ್ದೆಯನ್ನು ತಿಂದರೆ", [("ragi_mudde_piece", 1)]),
    ("ಮಸಾಲೆ ದೋಸೆ ಮತ್ತು ಕಾಫಿ", [("masala_dosa_piece", 1), ("filter_coffee_cup", 1)]),
    ("ಜೋಳದ ರೊಟ್ಟಿ ಮತ್ತು ಪಲ್ಯ", [("jowar_roti_piece", 1), ("mixed_veg_katori", 1)]),
]

# No food at all: common words must not match anything.
NO_FOOD = [
    "and now what?",
    "khana kab khaun",
    "मैं अब खाना खाऊँगा",
    "what if i walk 15 minutes after dinner",
    "how am i doing right now",
    "my sugar is 210, is that bad?",
    "ನನ್ನ ಸಕ್ಕರೆಯ ಮಟ್ಟ ಎಷ್ಟು?",
    "আমার সুগার এখন কত?",
    "when should I check next?",
    "I am fine, thank you",
]


@pytest.mark.parametrize("text,expected", CASES)
def test_dishes_found(text: str, expected: list[tuple[str, float]]) -> None:
    got = [(f["food_id"], f["units"]) for f in parse_foods(text)]
    assert got == [(fid, float(u)) for fid, u in expected], got


@pytest.mark.parametrize("text", NO_FOOD)
def test_no_false_positives(text: str) -> None:
    assert parse_foods(text) == []


def test_table_size() -> None:
    assert len(CASES) >= 30


def test_every_dish_is_findable_by_its_english_name() -> None:
    misses = []
    for _, r in food.table().iterrows():
        got = [f["food_id"] for f in food.find_in_text(r["name_en"])]
        if r["id"] not in got:
            misses.append((r["id"], r["name_en"], got))
    assert not misses, misses[:10]


@pytest.mark.parametrize("col", ["name_hi", "name_bn", "name_kn"])
def test_native_names_match_their_dish(col: str) -> None:
    """Each formal native name (with or without its parenthetical) resolves to a dish of the
    same base food; ambiguous short names may resolve to the everyday variant."""
    misses = []
    for _, r in food.table().iterrows():
        if food._norm(r[col]) in food.NEEDS_QTY:  # "चीनी" alone is ambiguous: needs "1 चम्मच चीनी"
            assert food.find_in_text(f"1 {r[col]}")[0]["food_id"] == r["id"]
            continue
        got = [f["food_id"] for f in food.find_in_text(r[col])]
        if not got:
            misses.append((r["id"], r[col]))
    assert not misses, misses[:10]


def test_match_handles_parenthetical_native_names() -> None:
    assert food.match("चावल")[0] == (RICE, 1.0)
    assert food.match("चावल (पका हुआ)")[0] == (RICE, 1.0)
    assert food.match("ভাত")[0] == (RICE, 1.0)


def test_search_returns_contract_fields() -> None:
    out = food.search("roti", "hi-IN")
    assert out and out[0]["id"] == ROTI
    for k in ("id", "name", "name_en", "unit", "unit_label", "grams_per_unit", "carbs_g", "fibre_g", "protein_g",
              "fat_g", "kcal", "cuisine"):
        assert k in out[0]
