from time import perf_counter
from fastapi.testclient import TestClient
from backend.app.main import create_app
from backend.app.repositories import InMemoryGraphRepository


def test_task_graph_and_audit_api(tmp_path):
    app = create_app(repository=InMemoryGraphRepository(), audit_path=tmp_path / 'audit.db', task_path=tmp_path / 'tasks.db', tokens={'secret-a': ('alice', 'analyst'), 'secret-b': ('bob', 'analyst'), 'audit-token': ('auditor', 'auditor')})
    with TestClient(app) as client:
        a = {'Authorization': 'Bearer secret-a'}
        b = {'Authorization': 'Bearer secret-b'}
        assert client.get('/api/v1/graph/persons', params={'task_id': 'missing'}).status_code == 401
        response = client.post('/api/v1/tasks/analyze', headers=a, json={'media_id': 'M1'})
        assert response.status_code == 201
        task = response.json()['data']['task_id']
        assert client.get(f'/api/v1/tasks/{task}', headers=b).status_code == 403
        assert client.post(f'/api/v1/tasks/{task}/cancel', headers=a).json()['data']['status'] == 'cancelled'
        assert client.post(f'/api/v1/tasks/{task}/retry', headers=a).json()['data']['status'] == 'queued'
        for person in ('P1', 'P2'):
            assert client.put(f'/api/v1/graph/persons/{person}', headers=a, json={'task_id': task, 'properties': {'name': 'Alice', 'version': 1}}).status_code == 200
        assert client.put('/api/v1/graph/relations/P1/P2', headers=a, json={'task_id': task, 'properties': {'strength': 0.5}}).status_code == 200
        start = perf_counter()
        result = client.get('/api/v1/graph/relations', headers=a, params={'task_id': task})
        assert perf_counter() - start < 1
        assert result.json()['data'][0]['strength'] == 0.5
        people = client.get('/api/v1/graph/persons', headers=a, params={'task_id': task}).json()['data']
        assert 'name' not in people[0]
        assert client.get('/api/v1/graph/persons', headers=b, params={'task_id': task}).status_code == 403
        assert client.get('/api/v1/audit/events', headers=a).status_code == 403
        events = client.get('/api/v1/audit/events', headers={'Authorization': 'Bearer audit-token'}).json()['data']
        assert any(event['outcome'] == 'denied' for event in events)
        assert 'secret-a' not in str(events)
        assert client.delete('/api/v1/graph/relations/P1/P2', headers=a, params={'task_id': task}).status_code == 200
        assert client.delete('/api/v1/graph/persons/P1', headers=a, params={'task_id': task}).status_code == 200


def test_database_failure_is_not_an_empty_graph(tmp_path):
    class Unavailable(InMemoryGraphRepository):
        def list_persons(self, task):
            from neo4j.exceptions import ServiceUnavailable
            raise ServiceUnavailable('offline')

    app = create_app(repository=Unavailable(), audit_path=tmp_path / 'a.db', task_path=tmp_path / 't.db', tokens={'token': ('alice', 'analyst')})
    with TestClient(app) as client:
        auth = {'Authorization': 'Bearer token'}
        task = client.post('/api/v1/tasks/analyze', headers=auth, json={'media_id': 'M'}).json()['data']['task_id']
        response = client.get('/api/v1/graph/persons', headers=auth, params={'task_id': task})
        assert response.status_code == 503
        assert response.json()['code'] == 50301


def test_multihop_endpoint_enforces_ownership_bounds_and_latency(tmp_path):
    repo = InMemoryGraphRepository()
    app = create_app(repository=repo, audit_path=tmp_path / 'a.db', task_path=tmp_path / 't.db', tokens={'a': ('alice', 'analyst'), 'b': ('bob', 'analyst')})
    with TestClient(app) as client:
        auth = {'Authorization': 'Bearer a'}
        task = client.post('/api/v1/tasks/analyze', headers=auth, json={'media_id': 'M'}).json()['data']['task_id']
        for person in ('A', 'B', 'C'):
            repo.put_person(task, person, {})
        repo.put_relation(task, 'A', 'B', {})
        repo.put_relation(task, 'B', 'C', {})
        url = '/api/v1/graph/persons/A/neighbors'
        start = perf_counter()
        response = client.get(url, headers=auth, params={'task_id': task, 'max_hops': 2})
        assert response.status_code == 200
        assert perf_counter() - start < 1
        assert response.json()['data'] == [{'person_id': 'B', 'hops': 1}, {'person_id': 'C', 'hops': 2}]
        assert client.get(url, headers={'Authorization': 'Bearer b'}, params={'task_id': task}).status_code == 403
        assert client.get(url, headers=auth, params={'task_id': task, 'max_hops': 5}).status_code == 422
        assert client.get('/api/v1/graph/persons/missing/neighbors', headers=auth, params={'task_id': task}).status_code == 404


def test_database_query_timeout_returns_explicit_504(tmp_path):
    from neo4j.exceptions import TransientError
    class TimedOut(TransientError):
        code = 'Neo.TransientError.Transaction.TransactionTimedOut'
    class SlowRepository(InMemoryGraphRepository):
        def neighbors(self, *args):
            raise TimedOut('time limit exceeded')
    app = create_app(repository=SlowRepository(), audit_path=tmp_path / 'a.db', task_path=tmp_path / 't.db', tokens={'a': ('alice', 'analyst')})
    with TestClient(app) as client:
        auth = {'Authorization': 'Bearer a'}
        task = client.post('/api/v1/tasks/analyze', headers=auth, json={'media_id': 'M'}).json()['data']['task_id']
        response = client.get('/api/v1/graph/persons/A/neighbors', headers=auth, params={'task_id': task})
        assert response.status_code == 504
        assert response.json()['code'] == 50401
