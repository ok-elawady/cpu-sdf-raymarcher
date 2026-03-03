import pytest

from cpu_sdf_raymarcher.common import color_utils as c


@pytest.mark.parametrize(
    "value, expected",
    [
        ("#A1B2C3", (161, 178, 195)),
        ("A1B2C3", (161, 178, 195)),
        ("0xA1B2C3", (161, 178, 195)),
        ("161,178,195", (161, 178, 195)),
        ((161, 178, 195), (161, 178, 195)),
        ([161, 178, 195], (161, 178, 195)),
    ],
)
def test_parse_color_literal_valid_formats(value, expected) -> None:
    assert c.parse_color_literal(value, "--color") == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        "#GGHHII",
        "12,34",
        "12,34,999",
        (1, 2),
        object(),
    ],
)
def test_parse_color_literal_invalid(value) -> None:
    with pytest.raises(ValueError):
        c.parse_color_literal(value, "--color")


def test_rgb_to_hex_and_unit_conversion_roundtrip() -> None:
    rgb = (10, 20, 30)
    assert c.rgb_to_hex(rgb) == "#0A141E"
    unit = c.to_unit_color(rgb)
    assert unit == pytest.approx((10 / 255.0, 20 / 255.0, 30 / 255.0))


def test_gamma_correct_and_color_to_bytes() -> None:
    corrected = c.gamma_correct((0.25, 0.5, 1.0))
    assert corrected[0] == pytest.approx(0.25 ** (1.0 / 2.2))
    assert corrected[1] == pytest.approx(0.5 ** (1.0 / 2.2))
    assert corrected[2] == pytest.approx(1.0)
    assert c.color_to_bytes((0.0, 0.5, 1.0)) == (0, 128, 255)
