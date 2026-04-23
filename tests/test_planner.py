from deep_framex.planning.planner import _intersect_windows, _sample_timestamps
from deep_framex.models.core import TimePeriod
from datetime import datetime, timezone

def test_intersect_windows():
    # Test intersecting time periods
    assert _intersect_windows([TimePeriod(start=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
                  end=datetime(2025, 1, 1, 10, 10, tzinfo=timezone.utc))],
      [TimePeriod(start=datetime(2025, 1, 1, 10, 5, tzinfo=timezone.utc),
                  end=datetime(2025, 1, 1, 10, 15, tzinfo=timezone.utc))],
    ) == [TimePeriod(start=datetime(2025, 1, 1, 10, 5, tzinfo=timezone.utc),
                    end=datetime(2025, 1, 1, 10, 10, tzinfo=timezone.utc))]
    
    # Test non-intersecting time periods
    assert _intersect_windows([TimePeriod(start=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
                  end=datetime(2025, 1, 1, 10, 5, tzinfo=timezone.utc))],
      [TimePeriod(start=datetime(2025, 1, 1, 10, 10, tzinfo=timezone.utc),
                  end=datetime(2025, 1, 1, 10, 15, tzinfo=timezone.utc))],
    ) == []
    
    # Test time period within time period
    assert _intersect_windows([TimePeriod(start=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
                  end=datetime(2025, 1, 1, 10, 20, tzinfo=timezone.utc))],
      [TimePeriod(start=datetime(2025, 1, 1, 10, 5, tzinfo=timezone.utc),
                  end=datetime(2025, 1, 1, 10, 10, tzinfo=timezone.utc))],
    ) == [TimePeriod(start=datetime(2025, 1, 1, 10, 5, tzinfo=timezone.utc),
                    end=datetime(2025, 1, 1, 10, 10, tzinfo=timezone.utc))]
    
    # Test single touching point
    assert _intersect_windows([TimePeriod(start=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
                  end=datetime(2025, 1, 1, 10, 10, tzinfo=timezone.utc))],
      [TimePeriod(start=datetime(2025, 1, 1, 10, 10, tzinfo=timezone.utc),
                  end=datetime(2025, 1, 1, 10, 15, tzinfo=timezone.utc))],
    ) == [TimePeriod(start=datetime(2025, 1, 1, 10, 10, tzinfo=timezone.utc),
                    end=datetime(2025, 1, 1, 10, 10, tzinfo=timezone.utc))]
 
def test_sample_timestamps():
    # Test should return one timestamp for zero duration
    assert _sample_timestamps([TimePeriod(start=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
                              end=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc))], 30.0,
                              datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc), 0.0,
                              ) == [datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc)]

    # Offset and interval should yield two datetimes here
    assert _sample_timestamps([TimePeriod(start=datetime(2025, 1, 1, 10, 9, tzinfo=timezone.utc),
                              end=datetime(2025, 1, 1, 10, 10, tzinfo=timezone.utc))], 30.0,
                              datetime(2025, 1, 1, 10, 9, tzinfo=timezone.utc), 10.0,
                              ) == [datetime(2025, 1, 1, 10, 9, 10, tzinfo=timezone.utc),
                                 datetime(2025, 1, 1, 10, 9, 40, tzinfo=timezone.utc)]

    # Empty list should return []
    assert _sample_timestamps([], 30.0,
                              datetime(2025, 1, 1, 10, 9, tzinfo=timezone.utc), 10.0,
                              ) == []

    # Offset and interval should yield two datetimes here
    assert _sample_timestamps([TimePeriod(start=datetime(2025, 1, 1, 10, 9, tzinfo=timezone.utc),
                              end=datetime(2025, 1, 1, 10, 10, tzinfo=timezone.utc))], 30.0,
                              datetime(2025, 1, 1, 10, 9, tzinfo=timezone.utc), 5000.0,
                              ) == []


