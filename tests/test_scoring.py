from math import isfinite

import pytest
from pydantic import ValidationError

from app.schemas import DIMENSIONS, Weights
from machine_learning_recommendation_system.services.scoring import (
    academic_score,
    chance_category,
    chance_range,
    chance_score,
    cosine_score,
    cost_score,
    distance_score,
    haversine,
)


def test_haversine_known_distance_and_same_point():
    assert haversine(0, 0, 0, 0) == 0
    assert haversine(0, 0, 0, 1) == pytest.approx(111.195, abs=0.01)
    assert haversine(0, 0, 0, 180) == pytest.approx(20015.114, abs=0.01)


def test_cosine_identity_orthogonal_zero():
    a = dict.fromkeys(DIMENSIONS, 0)
    b = a.copy()
    a["investigative"] = 100
    b["artistic"] = 100
    assert cosine_score(a, a) == 100
    assert cosine_score(a, b) == 0
    assert cosine_score(a, dict.fromkeys(DIMENSIONS, 0)) == 0


def test_distance_and_cost_monotonic_boundaries():
    assert distance_score(0, 10) == 100
    assert distance_score(10, 10) == 0
    assert distance_score(15, 10) == 0
    assert distance_score(2, 10) > distance_score(5, 10)
    assert cost_score(0, 0) == 100
    assert cost_score(100, 0) == 0
    assert cost_score(200, 100) == 50
    assert cost_score(500, 500) == 100


def test_academic_matches_contract():
    assert academic_score(85, 85) == 100
    assert academic_score(80, 85) == academic_score(90, 85) == 75
    assert academic_score(40, 85) == 0


@pytest.mark.parametrize("history", [(70, 80, 90), (80, 80, 90), (70, 80, 80), (80, 80, 80)])
def test_chance_monotonic_finite_even_degenerate(history):
    values = [chance_score(x, *history) for x in range(101)]
    assert values == sorted(values)
    assert all(isfinite(x) and 5 <= x <= 95 for x in values)


@pytest.mark.parametrize(
    "value,category", [(34.999, "ambisius"), (35, "realistis"), (70, "realistis"), (70.001, "aman")]
)
def test_category_thresholds(value, category):
    assert chance_category(value) == category


def test_uncertainty_widens_with_less_data():
    assert chance_range(50, 3) == (40, 60)
    assert chance_range(50, 1) == (30, 70)
    assert chance_range(50, 3, True) == (35, 65)


@pytest.mark.parametrize(
    "payload", [{"biaya": 0.9}, {"akademik": -0.1}, {"akademik": float("nan")}, {"foo": 1}]
)
def test_invalid_weights(payload):
    with pytest.raises(ValidationError):
        Weights(**payload)
