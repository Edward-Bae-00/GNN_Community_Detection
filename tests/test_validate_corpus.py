"""Focused tests for V9 hidden-org observability inference."""

import pytest

from scripts.data import validate_corpus


def _infer(rows, events):
    helper = getattr(validate_corpus, "_infer_observable_people", None)
    assert helper is not None, "validator observability helper is missing"
    return helper(rows, events)


def _org_rows(*members):
    return {
        person_id: {"org_id": org_id, "is_dark": str(is_dark).lower()}
        for person_id, org_id, is_dark in members
    }


def test_dark_dark_same_org_cotravel_is_not_observable():
    rows = _org_rows(("P1", "O1", True), ("P2", "O1", True))

    assert _infer(rows, [{"primary_person_id": "P1", "co_traveler_person_ids": "P2"}]) == set()


def test_dark_non_dark_same_org_cotravel_does_not_make_either_observable():
    rows = _org_rows(("P1", "O1", True), ("P2", "O1", False))

    assert _infer(rows, [{"primary_person_id": "P1", "co_traveler_person_ids": "P2"}]) == set()


def test_non_dark_same_org_cotravel_makes_both_observable():
    rows = _org_rows(("P1", "O1", False), ("P2", "O1", False))

    assert _infer(rows, [{"primary_person_id": "P1", "co_traveler_person_ids": "P2"}]) == {"P1", "P2"}


def test_cross_org_cotravel_is_ignored():
    rows = _org_rows(("P1", "O1", False), ("P2", "O2", False))

    assert _infer(rows, [{"primary_person_id": "P1", "co_traveler_person_ids": "P2"}]) == set()


def test_vehicle_groups_org_cotravelers_when_primary_has_no_org():
    rows = _org_rows(("P1", "O1", False), ("P2", "O1", False))
    events = [
        {
            "primary_person_id": "N1",
            "co_traveler_person_ids": "P1;P2",
            "vehicle_id": "V1",
        }
    ]

    assert _infer(rows, events) == {"P1", "P2"}


def test_vehicle_grouping_keeps_orgs_separate():
    rows = _org_rows(("P1", "O1", False), ("P2", "O2", False))
    events = [
        {
            "primary_person_id": "N1",
            "co_traveler_person_ids": "P1;P2",
            "vehicle_id": "V1",
        }
    ]

    assert _infer(rows, events) == set()


def test_carrier_grouping_keeps_orgs_separate():
    rows = _org_rows(("P1", "O1", False), ("P2", "O2", False))
    events = [
        {"primary_person_id": "P1", "co_traveler_person_ids": "", "carrier_id": "B1"},
        {"primary_person_id": "P2", "co_traveler_person_ids": "", "carrier_id": "B1"},
    ]

    assert _infer(rows, events) == set()


def test_carrier_evidence_counts_primaries_not_cotravelers():
    rows = _org_rows(("P1", "O1", False), ("P2", "O1", False))
    events = [
        {
            "primary_person_id": "N1",
            "co_traveler_person_ids": "P1",
            "carrier_id": "B1",
        },
        {"primary_person_id": "P2", "co_traveler_person_ids": "", "carrier_id": "B1"},
    ]

    assert _infer(rows, events) == set()


@pytest.mark.parametrize(
    "events",
    [
        [{"primary_person_id": "P1", "co_traveler_person_ids": "P2", "vehicle_id": "V1"}],
        [
            {"primary_person_id": "P1", "co_traveler_person_ids": "", "carrier_id": "B1"},
            {"primary_person_id": "P2", "co_traveler_person_ids": "", "carrier_id": "B1"},
        ],
    ],
    ids=["vehicle", "carrier"],
)
def test_groups_do_not_qualify_with_one_non_dark_member(events):
    rows = _org_rows(("P1", "O1", False), ("P2", "O1", True))

    assert _infer(rows, events) == set()


@pytest.mark.parametrize(
    "events",
    [
        [
            {"primary_person_id": "P1", "co_traveler_person_ids": "P2", "vehicle_id": "V1"},
            {"primary_person_id": "P3", "co_traveler_person_ids": "", "vehicle_id": "V1"},
        ],
        [
            {"primary_person_id": "P1", "co_traveler_person_ids": "", "carrier_id": "B1"},
            {"primary_person_id": "P2", "co_traveler_person_ids": "", "carrier_id": "B1"},
            {"primary_person_id": "P3", "co_traveler_person_ids": "", "carrier_id": "B1"},
        ],
    ],
    ids=["vehicle", "carrier"],
)
def test_groups_update_only_non_dark_members_after_threshold(events):
    rows = _org_rows(("P1", "O1", False), ("P2", "O1", True), ("P3", "O1", False))

    assert _infer(rows, events) == {"P1", "P3"}
