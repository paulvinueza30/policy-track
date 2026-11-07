from app.date_window import in_window, window_end, window_start


def test_window_is_four_years():
    start, end = window_start(), window_end()
    assert end.year - start.year == 4
    assert in_window(start.replace(year=start.year + 1))
