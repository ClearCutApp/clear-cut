"""Tests for the ten supported jurisdictions (docs/plan/sdd.md Section 2)."""

import pytest

from clearcut.domain.errors import UnknownJurisdiction
from clearcut.domain.jurisdiction import JURISDICTIONS, Jurisdiction, jurisdiction_for


def test_jurisdiction_for_ar_has_the_argentina_corpus_prefix():
    assert jurisdiction_for("AR").corpus_prefix == "argentina/"


def test_jurisdiction_for_unknown_code_raises_unknown_jurisdiction():
    with pytest.raises(UnknownJurisdiction):
        jurisdiction_for("ZZ")


def test_unknown_jurisdiction_is_not_a_key_error():
    assert not issubclass(UnknownJurisdiction, KeyError)


def test_the_module_exposes_exactly_the_ten_supported_jurisdictions():
    assert len(JURISDICTIONS) == 10
    assert {j.code for j in JURISDICTIONS} == {
        "AR",
        "US",
        "ES",
        "MX",
        "CA",
        "FR",
        "GB",
        "IN",
        "BR",
        "KR",
    }


def test_every_jurisdiction_carries_code_display_name_and_corpus_prefix():
    for j in JURISDICTIONS:
        assert isinstance(j, Jurisdiction)
        assert j.code
        assert j.display_name
        assert j.corpus_prefix.endswith("/")
