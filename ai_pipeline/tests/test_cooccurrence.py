import math
import pytest
from ai_pipeline.cooccurrence import compute_relations


def frame(t, duration=1.0, tracks=None):
    return {'timestamp': t, 'duration': duration, 'tracks': tracks if tracks is not None else [
        {'track_id': 'A', 'bbox': [0.0, 0.0, 0.2, 0.2]},
        {'track_id': 'B', 'bbox': [0.3, 0.0, 0.5, 0.2]}]}


def test_known_duration_distance_and_strength():
    result = compute_relations([frame(0), frame(1)], window_seconds=2)
    assert len(result) == 1
    edge = result[0]
    assert (edge['source'], edge['target']) == ('A', 'B')
    assert edge['co_occurrence_count'] == 2
    assert edge['total_duration_seconds'] == 2
    assert edge['avg_normalized_distance'] == pytest.approx(0.3)
    assert edge['strength'] == pytest.approx(0.76)


def test_frame_interval_is_split_at_half_open_window_boundary():
    result = compute_relations([frame(1.5)], window_seconds=2)
    assert [r['window_start'] for r in result] == [0, 2]
    assert [r['total_duration_seconds'] for r in result] == [0.5, 0.5]
    assert [r['window_end'] for r in result] == [2, 4]


def test_empty_single_and_missing_people_generate_no_self_edges():
    assert compute_relations([]) == []
    assert compute_relations([frame(0, tracks=[])]) == []
    assert compute_relations([frame(0, tracks=[{'track_id': 'A', 'bbox': [0, 0, 1, 1]}])]) == []


@pytest.mark.parametrize('bad_frames,kwargs', [
    ([frame(1), frame(0)], {}),
    ([frame(0), frame(0.5)], {}),
    ([frame(-1)], {}),
    ([frame(0, 0)], {}),
    ([frame(math.nan)], {}),
    ([frame(0)], {'window_seconds': 0}),
    ([frame(0)], {'distance_scale': 0}),
    ([frame(0, tracks=[{'track_id': 'A', 'bbox': [0, 0, 2, 1]}])], {}),
    ([frame(0, tracks=[{'track_id': 'A', 'bbox': [0, 0, 1, 1]}] * 2)], {}),
])
def test_invalid_observations_are_rejected(bad_frames, kwargs):
    with pytest.raises(ValueError):
        compute_relations(bad_frames, **kwargs)


def test_order_independence_of_track_pairs_and_missing_frame_duration():
    first = frame(0)
    second = frame(2)
    second['tracks'].reverse()
    result = compute_relations([first, second], window_seconds=4)
    assert len(result) == 1
    assert result[0]['total_duration_seconds'] == 2
    assert result[0]['strength'] == pytest.approx(0.46)


def test_decimal_frame_rates_do_not_create_false_overlap_errors():
    result = compute_relations([frame(i / 10, 0.1) for i in range(30)], window_seconds=1)
    assert len(result) == 3
    assert sum(r['total_duration_seconds'] for r in result) == pytest.approx(3)
