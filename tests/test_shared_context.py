import math

import pytest

from core.shared_context import DATA_NOT_INSTRUCTIONS, canonical_json, context_block, sha256_of


def test_key_order_does_not_change_the_text_or_the_hash():
    a = {"ticker": "XXXX", "financials": [{"revenue": 1, "cash": 2}], "as_of": "2026-10-14"}
    b = {"as_of": "2026-10-14", "financials": [{"cash": 2, "revenue": 1}], "ticker": "XXXX"}
    assert canonical_json(a) == canonical_json(b)
    assert sha256_of(canonical_json(a)) == sha256_of(canonical_json(b))


def test_any_change_in_the_data_changes_the_hash():
    assert sha256_of(canonical_json({"revenue": 1})) != sha256_of(canonical_json({"revenue": 1.0001}))


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_nan_and_infinity_are_refused_so_missing_data_stays_explicit(bad):
    with pytest.raises(ValueError):
        canonical_json({"gross_margin": bad})


def test_null_is_kept_as_null_not_zero():
    assert canonical_json({"gross_margin": None}) == '{"gross_margin":null}'


def test_non_ascii_text_is_kept_readable():
    assert canonical_json({"city": "Zürich – Šiaurė"}) == '{"city":"Zürich – Šiaurė"}'


def test_context_block_marks_the_content_as_data():
    block = context_block("data_pack", {"a": 1})
    assert block.startswith(DATA_NOT_INSTRUCTIONS.format(tag="data_pack"))
    assert block.endswith('<data_pack>\n{"a":1}\n</data_pack>')
