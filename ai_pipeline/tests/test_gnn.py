import math
import pytest
import torch
from ai_pipeline.gnn import RelationGNN, build_graph, predict_relations, save_checkpoint, load_checkpoint


MATRIX = [[0, 0.8, 0], [0.8, 0, 0.3], [0, 0.3, 0]]
FEATURES = [[1, 0], [0.5, 0.5], [0, 1]]


def test_build_pyg_graph_preserves_weighted_bidirectional_edges():
    graph = build_graph(MATRIX, FEATURES)
    assert graph.x.shape == (3, 2)
    assert graph.edge_index.tolist() == [[0, 1, 1, 2], [1, 0, 2, 1]]
    assert graph.edge_weight.tolist() == pytest.approx([0.8, 0.8, 0.3, 0.3])


def test_real_gcn_forward_is_symmetric_and_backpropagates():
    torch.manual_seed(11)
    model = RelationGNN(2, 4)
    graph = build_graph(MATRIX, FEATURES)
    logits = model(graph, torch.tensor([[0, 1], [1, 0]], dtype=torch.long))
    assert logits.shape == (2,)
    assert logits[0].item() == pytest.approx(logits[1].item())
    logits.sum().backward()
    assert model.conv1.lin.weight.grad is not None
    assert torch.isfinite(model.conv1.lin.weight.grad).all()


def test_inference_returns_known_probability_without_claiming_trained_accuracy():
    model = RelationGNN(2, 4)
    with torch.no_grad():
        for parameter in model.parameters():
            parameter.zero_()
        model.decoder[-1].bias.fill_(math.log(3))
    result = predict_relations(model, MATRIX, FEATURES, ['A', 'B', 'C'])
    assert [(r['source'], r['target']) for r in result] == [('A', 'B'), ('B', 'C')]
    assert [r['probability'] for r in result] == pytest.approx([0.75, 0.75])
    assert all(r['uncertain'] and r['model_status'] == 'untrained' for r in result)


def test_isolates_empty_edges_and_explicit_nonedge_candidates():
    model = RelationGNN(2, 4)
    assert predict_relations(model, [[0, 0], [0, 0]], [[1, 0], [0, 1]], ['A', 'B']) == []
    result = predict_relations(model, MATRIX, FEATURES, ['A', 'B', 'C'], pairs=[[0, 2]])
    assert len(result) == 1 and 0 <= result[0]['probability'] <= 1


@pytest.mark.parametrize('matrix,features', [
    ([[0, 1]], FEATURES),
    ([[0, 0.5], [0.1, 0]], [[1], [2]]),
    ([[1]], [[1]]),
    ([[0, -1], [-1, 0]], [[1], [2]]),
    ([[0]], [[float('nan')]]),
    ([[0]], []),
])
def test_invalid_graph_inputs_are_rejected(matrix, features):
    with pytest.raises(ValueError):
        build_graph(matrix, features)


@pytest.mark.parametrize('ids,pairs', [
    (['A', 'A', 'C'], None),
    (['A', 'B', 'C'], [[0, 0]]),
    (['A', 'B', 'C'], [[0, 4]]),
    (['A', 'B', 'C'], [[0, 1.5]]),
])
def test_invalid_identity_or_candidate_pairs_are_rejected(ids, pairs):
    with pytest.raises(ValueError):
        predict_relations(RelationGNN(2, 4), MATRIX, FEATURES, ids, pairs)


def test_checkpoint_preserves_weights_and_training_metadata(tmp_path):
    torch.manual_seed(4)
    model = RelationGNN(2, 4)
    path = tmp_path / 'gnn.pt'
    save_checkpoint(model, path, 'experiment-1', trained=True)
    restored = load_checkpoint(path)
    actual = predict_relations(restored, MATRIX, FEATURES, ['A', 'B', 'C'])
    expected = predict_relations(model, MATRIX, FEATURES, ['A', 'B', 'C'])
    assert [r['probability'] for r in actual] == pytest.approx([r['probability'] for r in expected])
    assert actual[0]['model_version'] == 'experiment-1'
    assert actual[0]['model_status'] == 'trained'
