"""Property test pemetaan timeframe & rentang waktu candle untuk backend MCP.

Property 1: setiap timeframe internal -> period MCP sah & deterministik.
Property 2: datetime_from < datetime_to, ISO 8601 valid, untuk count >= 1.
"""

import random
import unittest
from datetime import datetime

from src.backends.base import (
    map_timeframe_to_period,
    candle_time_range,
    _TIMEFRAME_TO_PERIOD,
)

_VALID_PERIODS = {"M1", "M5", "M15", "M30", "H1", "H4", "D1"}


class TestTimeframeMapping(unittest.TestCase):

    def test_all_supported_timeframes_map_to_valid_period(self):
        for tf in _TIMEFRAME_TO_PERIOD:
            period = map_timeframe_to_period(tf)
            self.assertIn(period, _VALID_PERIODS)

    def test_mapping_is_deterministic(self):
        for tf in list(_TIMEFRAME_TO_PERIOD) + ["m5", "h1", "UNKNOWN"]:
            first = map_timeframe_to_period(tf)
            for _ in range(5):
                self.assertEqual(map_timeframe_to_period(tf), first)

    def test_case_insensitive(self):
        self.assertEqual(map_timeframe_to_period("m15"), "M15")
        self.assertEqual(map_timeframe_to_period("h4"), "H4")

    def test_unknown_defaults_to_m5(self):
        self.assertEqual(map_timeframe_to_period("XYZ"), "M5")


class TestCandleRange(unittest.TestCase):

    def test_range_valid_for_random_inputs(self):
        random.seed(99)
        timeframes = list(_TIMEFRAME_TO_PERIOD)
        for _ in range(300):
            tf = random.choice(timeframes)
            count = random.randint(1, 5000)
            dt_from_s, dt_to_s = candle_time_range(tf, count)
            dt_from = datetime.fromisoformat(dt_from_s)
            dt_to = datetime.fromisoformat(dt_to_s)
            # Property 2: from < to
            self.assertLess(dt_from, dt_to, f"tf={tf} count={count}")

    def test_count_zero_or_negative_clamped(self):
        dt_from_s, dt_to_s = candle_time_range("M5", 0)
        self.assertLess(datetime.fromisoformat(dt_from_s), datetime.fromisoformat(dt_to_s))
        dt_from_s, dt_to_s = candle_time_range("M5", -10)
        self.assertLess(datetime.fromisoformat(dt_from_s), datetime.fromisoformat(dt_to_s))

    def test_iso_format_parseable(self):
        dt_from_s, dt_to_s = candle_time_range("H1", 100)
        # Tidak melempar berarti ISO valid.
        datetime.fromisoformat(dt_from_s)
        datetime.fromisoformat(dt_to_s)

    def test_larger_timeframe_wider_range(self):
        _, _ = candle_time_range("D1", 10)
        m5_from, m5_to = candle_time_range("M5", 100, now=datetime(2026, 1, 1, 12, 0, 0))
        d1_from, d1_to = candle_time_range("D1", 100, now=datetime(2026, 1, 1, 12, 0, 0))
        span_m5 = datetime.fromisoformat(m5_to) - datetime.fromisoformat(m5_from)
        span_d1 = datetime.fromisoformat(d1_to) - datetime.fromisoformat(d1_from)
        self.assertGreater(span_d1, span_m5)


if __name__ == "__main__":
    unittest.main()
