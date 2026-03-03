import pytest

from renderer.common import math_utils as m


def test_add_sub_mul() -> None:
    assert m.add((1.0, 2.0, 3.0), (4.0, 5.0, 6.0)) == (5.0, 7.0, 9.0)
    assert m.sub((4.0, 5.0, 6.0), (1.0, 2.0, 3.0)) == (3.0, 3.0, 3.0)
    assert m.mul((1.0, -2.0, 3.0), 2.5) == (2.5, -5.0, 7.5)


def test_dot_length_cross_normalize() -> None:
    assert m.dot((1.0, 2.0, 3.0), (4.0, 5.0, 6.0)) == 32.0
    assert m.length((3.0, 4.0, 0.0)) == pytest.approx(5.0)
    assert m.cross((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)) == (0.0, 0.0, 1.0)
    assert m.normalize((0.0, 3.0, 4.0)) == pytest.approx((0.0, 0.6, 0.8))


def test_normalize_zero_vector() -> None:
    assert m.normalize((0.0, 0.0, 0.0)) == (0.0, 0.0, 0.0)


def test_clamp_and_mix() -> None:
    assert m.clamp(-1.0, 0.0, 10.0) == 0.0
    assert m.clamp(11.0, 0.0, 10.0) == 10.0
    assert m.clamp(3.0, 0.0, 10.0) == 3.0
    assert m.mix(10.0, 20.0, 0.25) == pytest.approx(12.5)


def test_length2_and_length8() -> None:
    assert m.length2((3.0, 4.0)) == pytest.approx(5.0)
    expected_l8 = (abs(3.0) ** 8 + abs(4.0) ** 8) ** (1.0 / 8.0)
    assert m.length8((3.0, 4.0)) == pytest.approx(expected_l8)
