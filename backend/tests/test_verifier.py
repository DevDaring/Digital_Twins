"""Numeric grounding verifier (agent/verifier.py)."""

from __future__ import annotations

import pytest

from pratifalan.agent.verifier import extract_numbers, normalise_digits, verify

TOOLS = [{
    "estimate": 156.4, "band": {"lo": 131.2, "hi": 181.7}, "p_high_2h": {"p": 0.32, "lo": 0.2, "hi": 0.45},
    "peak": {"t": "2026-10-05T21:40", "value": 157.8}, "now": "2026-10-05T19:30",
    "expected_gain_pct": 23.4,
}]


@pytest.mark.parametrize("text,expected", [
    ("আপনার সুগার প্রায় ১৫৬", [156.0]),            # Bengali digits
    ("आपकी शुगर लगभग १५६ है", [156.0]),           # Devanagari digits
    ("ನಿಮ್ಮ ಸಕ್ಕರೆ ಸುಮಾರು ೧೫೬", [156.0]),          # Kannada digits
    ("between 131 and 182", [131.0, 182.0]),
    ("1,200 steps", [1200.0]),
    ("peak 157.8", [157.8]),
    ("at 9:40 pm", [9.0, 40.0]),
])
def test_extract_numbers(text: str, expected: list[float]) -> None:
    assert extract_numbers(text) == expected


def test_normalise_digits_all_scripts() -> None:
    assert normalise_digits("০১২৩৪৫৬৭৮৯ ०१२३४५६७८९ ೦೧೨೩೪೫೬೭೮೯") == "0123456789 0123456789 0123456789"


@pytest.mark.parametrize("reply", [
    "Right now your glucose is about 156, most likely between 131 and 182.",
    "এখন আপনার সুগার প্রায় ১৫৬, সম্ভবত ১৩১ থেকে ১৮২-এর মধ্যে।",
    "अभी आपकी शुगर लगभग १५६ है, ज़्यादातर १३१ से १८२ के बीच।",
    "ಈಗ ನಿಮ್ಮ ಸಕ್ಕರೆ ಸುಮಾರು ೧೫೬, ಹೆಚ್ಚಾಗಿ ೧೩೧ ಮತ್ತು ೧೮೨ ನಡುವೆ.",
    "Your glucose may peak near 158 around 9:40 pm.",           # rounding + time from an ISO string
    "It may peak at about 160 around 9:40 pm.",                 # 157.8 -> "about 160" is fine
    "The chance of going above 180 is about 3 times out of 10.",  # p=0.32 -> "3 in 10"
    "The chance is 32 percent; the next reading cuts uncertainty by 23 percent.",
    "Less than 1 time in 10; call 108 in an emergency; target 70 to 180.",
])
def test_grounded_replies_pass(reply: str) -> None:
    g = verify(reply, TOOLS)
    assert g["passed"], g


@pytest.mark.parametrize("reply,bad", [
    ("Your glucose will reach 250 tonight.", "250"),
    ("It may peak near 170.", "170"),          # 157.8 is not "about 170"
    ("Take a reading at 6:15 am.", "15"),      # 6 is not a tool time either, 15 definitely not
    ("আপনার সুগার ২১০ হতে পারে", "210"),       # Bengali digits, ungrounded
    ("The chance is 55 percent.", "55"),
])
def test_ungrounded_numbers_caught(reply: str, bad: str) -> None:
    g = verify(reply, TOOLS)
    assert not g["passed"]
    assert bad in g["ungrounded"]


def test_numbers_from_user_message_are_allowed() -> None:
    g = verify("Thanks, I added your reading of 212.", TOOLS, user_text="my sugar is २१२")
    assert g["passed"], g


def test_signed_change_is_grounded() -> None:
    g = verify("Your peak changes by -12 and the chance moves from 62 to 50 percent.",
               [{"delta_peak": -12.3, "p_high_baseline": 0.618, "p_high_scenario": 0.502}])
    assert g["passed"], g


@pytest.mark.parametrize("text,lang,problems", [
    ("Your peak may reach 180 around 9 pm.", "en-IN", []),
    ("ok.", "en-IN", ["too_short"]),
    ("Your peak may reach 180 around", "en-IN", ["unfinished"]),
    ("Peak 175:\nYour sugar may rise tonight.", "en-IN", ["fragment_line"]),
    ("180:\nYour sugar may rise tonight.", "en-IN", ["fragment_line"]),
    ("आपकी शुगर लगभग 155 है।", "hi-IN", []),
    ("Your sugar is about 155 today.", "hi-IN", ["wrong_script"]),
    ("এখন সুগার প্রায় ১৫৫ (HbA1c)।", "bn-IN", []),
    ("ಈಗ ನಿಮ್ಮ ಸಕ್ಕರೆ ಸುಮಾರು 155 ಇದೆ.", "kn-IN", []),
    ("ಈಗ ನಿಮ್ಮ ಸಕ್ಕರೆ ಸುಮಾರು 155 ಇದೆ", "kn-IN", ["unfinished"]),
])
def test_sanity(text: str, lang: str, problems: list[str]) -> None:
    from pratifalan.agent.verifier import sanity

    assert sanity(text, lang) == problems
