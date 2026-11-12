import torch
from torch import nn
from torch_geometric.data import Data
from torch_geometric.nn import GCNConv


def build_graph(cooccurrence, entity_features):
    matrix = torch.as_tensor(cooccurrence, dtype=torch.float32, device='cpu')
    features = torch.as_tensor(entity_features, dtype=torch.float32, device='cpu')
    if features.ndim != 2 or min(features.shape) < 1 or matrix.shape != (features.shape[0], features.shape[0]):
        raise ValueError('expected N by N matrix and nonempty N by F entity features')
    if not torch.isfinite(features).all() or not torch.isfinite(matrix).all():
        raise ValueError('features and matrix must be finite')
    if (matrix < 0).any() or (matrix > 1).any() or matrix.diagonal().any() or not torch.allclose(matrix, matrix.T, atol=1e-6, rtol=0):
        raise ValueError('cooccurrence must be symmetric, normalized to [0,1], with zero diagonal')
    edge_index = matrix.nonzero().T.contiguous()
    edge_weight = matrix[edge_index[0], edge_index[1]]
    return Data(x=features, edge_index=edge_index, edge_weight=edge_weight, cooccurrence=matrix)


class RelationGNN(nn.Module):
    def __init__(self, input_dim, hidden_dim=16):
        super().__init__()
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.conv1 = GCNConv(input_dim, hidden_dim)
        self.conv2 = GCNConv(hidden_dim, hidden_dim)
        self.decoder = nn.Sequential(nn.Linear(hidden_dim + 1, hidden_dim), nn.ReLU(), nn.Linear(hidden_dim, 1))
        self.model_version = 'gnn-experimental-v1'
        self.trained = False

    def forward(self, graph, pairs):
        hidden = self.conv1(graph.x, graph.edge_index, graph.edge_weight).relu()
        hidden = self.conv2(hidden, graph.edge_index, graph.edge_weight)
        source, target = pairs[:, 0], pairs[:, 1]
        symmetric_features = hidden[source] * hidden[target]
        cooccurrence = graph.cooccurrence[source, target].unsqueeze(1)
        return self.decoder(torch.cat((symmetric_features, cooccurrence), dim=1)).squeeze(1)


@torch.inference_mode()
def predict_relations(model, cooccurrence, entity_features, person_ids, pairs=None):
    graph = build_graph(cooccurrence, entity_features)
    size = graph.num_nodes
    if len(person_ids) != size or any(not isinstance(p, str) or not p for p in person_ids) or len(set(person_ids)) != size:
        raise ValueError('provide one distinct nonempty person ID per feature row')
    if graph.x.shape[1] != model.input_dim:
        raise ValueError('feature dimension does not match model')
    if pairs is None:
        candidates = torch.triu(graph.cooccurrence, diagonal=1).nonzero()
    else:
        candidates = torch.as_tensor(pairs)
        if candidates.numel() == 0:
            candidates = torch.empty((0, 2), dtype=torch.long)
        if candidates.ndim != 2 or candidates.shape[1] != 2 or candidates.dtype not in (torch.int32, torch.int64):
            raise ValueError('pairs must be integer node index pairs')
        if (candidates < 0).any() or (candidates >= size).any() or (candidates[:, 0] == candidates[:, 1]).any():
            raise ValueError('candidate nodes must exist and differ')
    if not len(candidates):
        return []
    device = next(model.parameters()).device
    model.eval()
    probabilities = model(graph.to(device), candidates.to(device)).sigmoid().cpu().tolist()
    if not all(0 <= value <= 1 for value in probabilities):
        raise ValueError('model produced invalid probabilities')
    return [{'source': person_ids[int(pair[0])], 'target': person_ids[int(pair[1])],
             'probability': probability, 'uncertain': not model.trained or 0.45 <= probability <= 0.55,
             'model_version': model.model_version, 'model_status': 'trained' if model.trained else 'untrained'}
            for pair, probability in zip(candidates.cpu().tolist(), probabilities, strict=True)]


def save_checkpoint(model, path, model_version, trained=False):
    torch.save({'input_dim': model.input_dim, 'hidden_dim': model.hidden_dim,
                'model_version': model_version, 'trained': trained, 'state_dict': model.state_dict()}, path)


def load_checkpoint(path):
    checkpoint = torch.load(path, map_location='cpu', weights_only=True)
    model = RelationGNN(checkpoint['input_dim'], checkpoint['hidden_dim'])
    model.load_state_dict(checkpoint['state_dict'])
    model.model_version = checkpoint['model_version']
    model.trained = checkpoint['trained']
    return model
