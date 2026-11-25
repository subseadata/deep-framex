import math

import pytest

from deep_framex.utils.distance import EARTH_RADIUS_M, cumulative_distance, haversine_m

# One degree of arc on the sphere the module uses, metres.
DEGREE_M = math.radians(1.0) * EARTH_RADIUS_M


# Identical positions are 0 m apart, in every convention.
def test_haversine_identical_points_are_zero():
    assert haversine_m(27.1, -165.4, 27.1, -165.4) == 0.0
    assert haversine_m(0.0, 0.0, 0.0, 0.0) == 0.0
    assert haversine_m(-60.0, 359.9999, -60.0, 359.9999) == 0.0


# One degree of latitude is one degree of arc, wherever you are.
def test_haversine_one_degree_of_latitude():
    assert haversine_m(0.0, 0.0, 1.0, 0.0) == pytest.approx(DEGREE_M, rel=1e-9)
    assert haversine_m(30.0, -165.0, 31.0, -165.0) == pytest.approx(DEGREE_M, rel=1e-6)


# One degree of longitude shrinks with latitude, and matches an independent
# great-circle calculation. It is slightly shorter than DEGREE_M * cos(lat),
# because the great circle between the two fixes cuts toward the equator rather
# than following the parallel.
def test_haversine_one_degree_of_longitude_shrinks_with_latitude():
    assert haversine_m(0.0, 0.0, 0.0, 1.0) == pytest.approx(DEGREE_M, rel=1e-9)

    lat, d_lon = math.radians(60.0), math.radians(1.0)
    great_circle = EARTH_RADIUS_M * math.acos(
        math.sin(lat) ** 2 + math.cos(lat) ** 2 * math.cos(d_lon)
    )
    assert haversine_m(60.0, 0.0, 60.0, 1.0) == pytest.approx(great_circle, rel=1e-12)
    assert haversine_m(60.0, 0.0, 60.0, 1.0) < DEGREE_M * 0.5


# A 0-360 longitude log must not charge a crossing of the antimeridian as a
# crossing of most of the globe.
def test_haversine_handles_0_360_longitude():
    short = haversine_m(0.0, -0.0001, 0.0, 0.0001)
    assert haversine_m(0.0, 359.9999, 0.0, 0.0001) == pytest.approx(short, rel=1e-9)
    assert short == pytest.approx(DEGREE_M * 0.0002, rel=1e-6)


# ROV-scale steps: 1e-4 degrees of latitude is about 11 m.
def test_haversine_rov_scale_step():
    assert haversine_m(27.112684, -165.447109, 27.112784, -165.447109) == pytest.approx(
        DEGREE_M * 1e-4, rel=1e-6
    )


# The metric is the sphere the module declares, not a rounded 6371 km.
def test_haversine_uses_declared_earth_radius():
    assert haversine_m(0.0, 0.0, 0.0, 1.0) == pytest.approx(math.radians(1.0) * EARTH_RADIUS_M,
                                                            rel=1e-12)


# cumulative_distance: an empty log and a single fix.
def test_cumulative_distance_empty_and_single():
    assert cumulative_distance([]) == []
    assert cumulative_distance([(27.0, -165.0)]) == [0.0]


# The first fix is 0 m and the total grows by the Haversine step each row.
def test_cumulative_distance_accumulates_steps():
    rows = [
        (27.0000, -165.0),
        (27.0001, -165.0),
        (27.0001, -164.9999),
    ]
    totals = cumulative_distance(rows)
    assert totals[0] == 0.0
    assert totals[1] == pytest.approx(haversine_m(27.0, -165.0, 27.0001, -165.0), rel=1e-12)
    assert totals[2] == pytest.approx(totals[1] + haversine_m(
        27.0001, -165.0, 27.0001, -164.9999), rel=1e-12)


# A stationary vehicle travels nothing: repeated fixes add nothing.
def test_cumulative_distance_ignores_repeated_positions():
    rows = [(27.0, -165.0)] * 5
    assert cumulative_distance(rows) == [0.0] * 5


# Distance is an odometer, not a displacement: a run out and back counts twice.
def test_cumulative_distance_counts_reverse_travel():
    there = haversine_m(27.0, -165.0, 27.001, -165.0)
    totals = cumulative_distance([
        (27.0, -165.0),
        (27.001, -165.0),
        (27.0, -165.0),
    ])
    assert totals == pytest.approx([0.0, there, 2 * there], rel=1e-12)


# The result is non-decreasing by construction, whatever the track does.
def test_cumulative_distance_is_monotonic():
    rows = [
        (27.0, -165.0),
        (27.01, -165.0),
        (27.005, -165.02),
        (27.005, -165.02),
        (27.02, -165.05),
    ]
    totals = cumulative_distance(rows)
    assert all(b >= a for a, b in zip(totals, totals[1:]))
