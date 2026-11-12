import pytest
import json
import sys
from ai_pipeline.gnn import RelationGNN
from ai_pipeline.gnn_run import infer_m2_report, main


def test_m2_window_bridge_preserves_windows_and_synthetic_provenance():
    report = {'synthetic': True, 'relations': [
        {'source': 'A', 'target': 'B', 'strength': 0.8, 'window_start': 0, 'window_end': 10},
        {'source': 'B', 'target': 'C', 'strength': 0.2, 'window_start': 10, 'window_end': 20}]}
    result = infer_m2_report(RelationGNN(2, 4), report, {'A': [1, 0], 'B': [0.5, 0.5], 'C': [0, 1]})
    assert result['synthetic_input'] is True
    assert len(result['windows']) == 2
    assert result['windows'][0]['predictions'][0]['source'] == 'A'
    assert result['windows'][1]['predictions'][0]['source'] == 'B'
    assert result['windows'][1]['window_start'] == 10
    assert result['windows'][0]['predictions'][0]['model_status'] == 'untrained'


def test_m2_missing_features_fail_instead_of_fabricating_embeddings():
    report = {'synthetic': True, 'relations': [{'source': 'A', 'target': 'B', 'strength': 0.8, 'window_start': 0, 'window_end': 10}]}
    with pytest.raises(ValueError):
        infer_m2_report(RelationGNN(2), report, {'A': [1, 0]})


def test_m2_duplicate_edges_in_a_window_are_rejected():
    edge = {'source': 'A', 'target': 'B', 'strength': 0.8, 'window_start': 0, 'window_end': 10}
    with pytest.raises(ValueError):
        infer_m2_report(RelationGNN(2), {'synthetic': True, 'relations': [edge, edge]}, {'A': [1, 0], 'B': [0, 1]})


def test_gnn_command_writes_explicitly_untrained_demo(tmp_path, monkeypatch):
    source, features, output = (tmp_path / filename for filename in ('m2.json', 'features.json', 'm3.json'))
    source.write_text(json.dumps({'synthetic': True, 'relations': [{'source': 'A', 'target': 'B', 'strength': 0.4, 'window_start': 0, 'window_end': 1}]}))
    features.write_text(json.dumps({'A': [1, 0], 'B': [0, 1]}))
    monkeypatch.setattr(sys, 'argv', ['gnn_run', '--input', str(source), '--features', str(features), '--output', str(output)])
    main()
    result = json.loads(output.read_text(encoding='utf-8'))
    assert result['synthetic_input'] is True
    assert result['windows'][0]['predictions'][0]['model_status'] == 'untrained'
