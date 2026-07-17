from paperi.ui.main_window import _format_eta


def test_format_eta_under_a_minute() -> None:
    assert _format_eta(12) == "00:12"


def test_format_eta_over_a_minute() -> None:
    assert _format_eta(75) == "01:15"


def test_format_eta_rounds_fractional_seconds() -> None:
    assert _format_eta(12.6) == "00:13"


def test_format_eta_clamps_negative_to_zero() -> None:
    # Shouldn't happen in practice (a rate/remaining-chunks computation
    # gone wrong), but a negative ETA rendering as "-1:-5" would be a
    # worse failure mode than clamping to zero.
    assert _format_eta(-5) == "00:00"
