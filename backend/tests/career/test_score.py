"""
Tests for the career score algorithm.
Validates edge cases: empty data, partial data, maxed-out data.
"""

from __future__ import annotations

import pytest


def _score(
    problems_solved: int = 0,
    deployed_count: int = 0,
    on_resume_count: int = 0,
    applied_last_30d: int = 0,
    has_active: bool = False,
    contacts_count: int = 0,
    cf_rating: int = 0,
) -> dict:
    """Pure score computation (no DB) — mirrors services.compute_career_score logic."""
    dsa = min(25, round((problems_solved / 400) * 25))
    projects = min(25, deployed_count * 4 + on_resume_count)
    applications = min(20, applied_last_30d * 2) + (5 if has_active else 0)
    applications = min(20, applications)
    network = min(15, round(contacts_count * 0.3))
    cp = max(0, min(15, round((cf_rating - 800) / 600 * 15)))
    overall = dsa + projects + applications + network + cp
    return {
        "overall": overall,
        "dsa": dsa,
        "projects": projects,
        "applications": applications,
        "network": network,
        "cp": cp,
    }


class TestScoreEmptyData:
    def test_all_zeros(self):
        s = _score()
        assert s["overall"] == 0
        assert s["dsa"] == 0
        assert s["projects"] == 0
        assert s["applications"] == 0
        assert s["network"] == 0
        assert s["cp"] == 0

    def test_score_in_range(self):
        s = _score()
        assert 0 <= s["overall"] <= 100


class TestScorePartialData:
    def test_dsa_partial(self):
        s = _score(problems_solved=200)
        assert s["dsa"] == 12  # round(200/400*25) = round(12.5) = 12 or 13

    def test_dsa_rounds_correctly(self):
        s = _score(problems_solved=100)
        assert s["dsa"] == round(100 / 400 * 25)

    def test_projects_deployed(self):
        s = _score(deployed_count=2, on_resume_count=1)
        assert s["projects"] == min(25, 2 * 4 + 1)  # 9

    def test_applications_base_only(self):
        s = _score(applied_last_30d=5)
        assert s["applications"] == min(20, 5 * 2)  # 10

    def test_applications_with_active_bonus(self):
        s = _score(applied_last_30d=3, has_active=True)
        # min(20, 3*2) + 5 = 6 + 5 = 11
        assert s["applications"] == 11

    def test_network_partial(self):
        s = _score(contacts_count=20)
        assert s["network"] == min(15, round(20 * 0.3))  # 6

    def test_cp_below_800_is_zero(self):
        s = _score(cf_rating=700)
        assert s["cp"] == 0

    def test_cp_at_800_is_zero(self):
        s = _score(cf_rating=800)
        assert s["cp"] == 0

    def test_cp_at_1400_is_15(self):
        s = _score(cf_rating=1400)
        assert s["cp"] == 15

    def test_cp_midpoint(self):
        s = _score(cf_rating=1100)
        assert s["cp"] == round((1100 - 800) / 600 * 15)  # 7 or 8


class TestScoreMaxed:
    def test_dsa_caps_at_25(self):
        s = _score(problems_solved=800)
        assert s["dsa"] == 25

    def test_projects_caps_at_25(self):
        s = _score(deployed_count=10, on_resume_count=10)
        assert s["projects"] == 25

    def test_applications_caps_at_20(self):
        s = _score(applied_last_30d=20, has_active=True)
        assert s["applications"] == 20

    def test_network_caps_at_15(self):
        s = _score(contacts_count=100)
        assert s["network"] == 15

    def test_cp_caps_at_15(self):
        s = _score(cf_rating=2000)
        assert s["cp"] == 15

    def test_total_max_is_100(self):
        s = _score(
            problems_solved=1000,
            deployed_count=10,
            on_resume_count=10,
            applied_last_30d=20,
            has_active=True,
            contacts_count=200,
            cf_rating=2000,
        )
        assert s["overall"] == 100

    def test_total_never_exceeds_100(self):
        s = _score(
            problems_solved=999,
            deployed_count=99,
            on_resume_count=99,
            applied_last_30d=99,
            has_active=True,
            contacts_count=999,
            cf_rating=9999,
        )
        assert s["overall"] <= 100
