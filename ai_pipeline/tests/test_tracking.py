from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest
from ai_pipeline.tracking import MockTracker, YOLOByteTrack


def test_mock_tracks_have_stable_ids_and_normalized_coordinates():
    tracker = MockTracker()
    first, second = tracker.track(None), tracker.track(None)
    assert [p['track_id'] for p in first] == ['mock-1', 'mock-2']
    assert [p['track_id'] for p in second] == ['mock-1', 'mock-2']
    assert first[0]['bbox'] != second[0]['bbox']
    assert all(0 <= value <= 1 for p in second for value in p['bbox'])


def test_yolo_adapter_uses_bytetrack_person_filter_and_persistent_ids(tmp_path):
    weights = tmp_path / 'local.pt'
    weights.touch()
    model = MagicMock()
    boxes = SimpleNamespace(id=MagicMock(), xyxyn=MagicMock())
    boxes.id.cpu.return_value.tolist.return_value = [7]
    boxes.xyxyn.cpu.return_value.tolist.return_value = [[0.1, 0.2, 0.3, 0.4]]
    model.track.return_value = [SimpleNamespace(boxes=boxes)]
    tracker = YOLOByteTrack(weights, model=model)
    assert tracker.track('image') == [{'track_id': 'track-7', 'bbox': [0.1, 0.2, 0.3, 0.4]}]
    args = model.track.call_args.kwargs
    assert args['tracker'] == 'bytetrack.yaml'
    assert args['classes'] == [0]
    assert args['persist'] is True
    boxes.id = None
    assert tracker.track('image') == []


def test_yolo_requires_existing_weights_instead_of_downloading(tmp_path):
    with pytest.raises(FileNotFoundError):
        YOLOByteTrack(tmp_path / 'missing.pt')
