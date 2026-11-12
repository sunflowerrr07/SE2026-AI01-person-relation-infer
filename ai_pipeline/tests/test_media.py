import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest
from ai_pipeline.media import iter_frames
from ai_pipeline.run import run_pipeline


def images(tmp_path):
    folder = tmp_path / 'images'
    folder.mkdir()
    for number in (10, 2, 1):
        assert cv2.imwrite(str(folder / f'frame{number}.png'), np.full((32, 48, 3), number, dtype=np.uint8))
    return folder


def test_images_use_natural_order_fps_and_frame_limit(tmp_path):
    frames = list(iter_frames(images(tmp_path), fps=2, max_frames=2))
    assert [int(f['image'][0, 0, 0]) for f in frames] == [1, 2]
    assert [f['timestamp'] for f in frames] == [0, 0.5]
    assert [f['duration'] for f in frames] == [0.5, 0.5]


def test_video_decodes_with_its_own_frame_rate(tmp_path):
    path = tmp_path / 'short.avi'
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'MJPG'), 5, (48, 32))
    assert writer.isOpened(), 'MJPG writer required for this test'
    try:
        for _ in range(3):
            writer.write(np.zeros((32, 48, 3), dtype=np.uint8))
    finally:
        writer.release()
    frames = list(iter_frames(path))
    assert len(frames) == 3
    assert frames[1]['timestamp'] == pytest.approx(0.2)
    assert frames[0]['duration'] == pytest.approx(0.2)


@pytest.mark.parametrize('fps,max_frames', [(0, 3), (float('nan'), 3), (1, 0)])
def test_invalid_media_parameters_are_rejected(tmp_path, fps, max_frames):
    with pytest.raises(ValueError):
        list(iter_frames(images(tmp_path), fps=fps, max_frames=max_frames))


def test_missing_empty_and_corrupt_inputs_are_rejected(tmp_path):
    with pytest.raises(FileNotFoundError):
        list(iter_frames(tmp_path / 'missing.mp4'))
    with pytest.raises(ValueError):
        list(iter_frames(tmp_path))
    bad = tmp_path / 'bad.png'
    bad.write_text('not an image')
    with pytest.raises(ValueError):
        list(iter_frames(bad))


def test_mock_pipeline_and_cli_mark_synthetic_evidence(tmp_path):
    folder = images(tmp_path)
    result = run_pipeline(folder, fps=10, window_seconds=1)
    assert result['mode'] == 'mock'
    assert result['synthetic'] is True
    assert result['frames_processed'] == 3
    assert result['relations'][0]['total_duration_seconds'] == pytest.approx(0.3)
    assert result['relations'][0]['strength'] == pytest.approx(0.42)
    output = tmp_path / 'result.json'
    completed = subprocess.run([sys.executable, '-m', 'ai_pipeline.run', '--source', str(folder), '--output', str(output), '--window-seconds', '1'], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(output.read_text(encoding='utf-8'))['synthetic'] is True


def test_pipeline_rejects_unknown_mode(tmp_path):
    with pytest.raises(ValueError):
        run_pipeline(images(tmp_path), mode='typo')
