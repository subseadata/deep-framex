from deep_framex.utils.coordinates import normalize_longitude, decimal_to_ref, decimal_to_dms
import pytest

def test_normalize_longitude():
    assert normalize_longitude(-45.0) == -45.0
    assert normalize_longitude(180.0) == 180.0
    assert normalize_longitude(200.0) == -160.0

def test_decimal_to_ref():
    assert decimal_to_ref(50.0, "lat") == "N"
    assert decimal_to_ref(-30.0, "lat") == "S"
    assert decimal_to_ref(20.0, "lon") == "E"
    assert decimal_to_ref(-10.0, "lon") == "W"

    with pytest.raises(ValueError):
        decimal_to_ref(45.0, "longitude")

def test_decimal_to_dms():
    assert decimal_to_dms(45.263) == ((45, 1), (15, 1), (468000, 10000))
