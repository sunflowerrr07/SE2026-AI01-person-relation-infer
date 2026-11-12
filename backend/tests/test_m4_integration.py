from fastapi.testclient import TestClient
from backend.app.main import create_app
from backend.app.repositories import InMemoryGraphRepository


PNG = bytes.fromhex('89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de0000000c4944415408d763f8cfc000000301010018dd8db00000000049454e44ae426082')


def client_for(tmp_path):
    app = create_app(repository=InMemoryGraphRepository(), audit_path=tmp_path / 'audit.sqlite3', task_path=tmp_path / 'tasks.sqlite3', tokens={'analyst': ('alice', 'analyst'), 'other': ('bob', 'analyst'), 'auditor': ('eve', 'auditor')})
    return TestClient(app)


def test_cors_allows_local_frontend_only(tmp_path):
    with client_for(tmp_path) as client:
        response = client.options('/api/v1/tasks', headers={'Origin': 'http://localhost:5173', 'Access-Control-Request-Method': 'GET', 'Access-Control-Request-Headers': 'authorization'})
        assert response.status_code == 200
        assert response.headers['access-control-allow-origin'] == 'http://localhost:5173'
        forbidden = client.options('/api/v1/tasks', headers={'Origin': 'https://example.org', 'Access-Control-Request-Method': 'GET'})
        assert 'access-control-allow-origin' not in forbidden.headers


def test_upload_task_mock_inference_graph_and_audit(tmp_path):
    with client_for(tmp_path) as client:
        auth = {'Authorization': 'Bearer analyst'}
        upload = client.post('/api/v1/media', headers=auth, files={'file': ('sample.png', PNG, 'image/png')}, data={'authorized': 'true'})
        assert upload.status_code == 201, upload.text
        media_id = upload.json()['data']['media_id']
        task = client.post('/api/v1/tasks/analyze', headers=auth, json={'media_id': media_id}).json()['data']['task_id']
        response = client.post(f'/api/v1/tasks/{task}/run-demo', headers=auth)
        assert response.status_code == 202, response.text
        state = client.get(f'/api/v1/tasks/{task}', headers=auth).json()['data']
        assert state['status'] == 'succeeded', state
        assert state['progress'] == 100
        result = client.get(f'/api/v1/tasks/{task}/result', headers=auth).json()['data']
        assert result['synthetic_input'] is True
        assert result['windows'][0]['predictions'][0]['model_status'] == 'untrained'
        people = client.get('/api/v1/graph/persons', headers=auth, params={'task_id': task}).json()['data']
        assert len(people) == 2
        edges = client.get('/api/v1/graph/relations', headers=auth, params={'task_id': task}).json()['data']
        assert edges[0]['uncertain'] is True
        assert client.get(f'/api/v1/tasks/{task}/result', headers={'Authorization': 'Bearer other'}).status_code == 403
        events = client.get('/api/v1/audit/events', headers={'Authorization': 'Bearer auditor'}).json()['data']
        assert any(event['target'] == '/api/v1/media' for event in events)
        assert 'sample.png' not in str(events)


def test_upload_rejects_missing_authorization_and_invalid_files(tmp_path):
    with client_for(tmp_path) as client:
        auth = {'Authorization': 'Bearer analyst'}
        assert client.post('/api/v1/media', headers=auth, files={'file': ('x.png', PNG, 'image/png')}, data={'authorized': 'false'}).status_code == 403
        assert client.post('/api/v1/media', headers=auth, files={'file': ('x.png', b'invalid', 'image/png')}, data={'authorized': 'true'}).status_code == 422


def test_demo_failure_records_failed_status(tmp_path, monkeypatch):
    import ai_pipeline.run
    def fail(*args, **kwargs):
        raise RuntimeError('model failure')
    monkeypatch.setattr(ai_pipeline.run, 'run_pipeline', fail)
    with client_for(tmp_path) as client:
        auth = {'Authorization': 'Bearer analyst'}
        media = client.post('/api/v1/media', headers=auth, files={'file': ('x.png', PNG, 'image/png')}, data={'authorized': 'true'}).json()['data']['media_id']
        task = client.post('/api/v1/tasks/analyze', headers=auth, json={'media_id': media}).json()['data']['task_id']
        client.post(f'/api/v1/tasks/{task}/run-demo', headers=auth)
        status = client.get(f'/api/v1/tasks/{task}', headers=auth).json()['data']
        assert status['status'] == 'failed'
        assert status['error']
        assert client.get(f'/api/v1/tasks/{task}/result', headers=auth).status_code == 409
