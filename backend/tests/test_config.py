import pytest
from backend.app.config import create_configured_app, create_from_environment


def test_configuration_fails_closed_without_credentials(tmp_path):
    with pytest.raises(ValueError):
        create_configured_app({'APP_DATA_DIR': str(tmp_path)})


def test_memory_mode_requires_explicit_credentials(tmp_path):
    app = create_configured_app({'APP_DATA_DIR': str(tmp_path), 'API_TOKEN': 'a-long-test-token', 'API_USER': 'alice'})
    assert app is not None


def test_unknown_repository_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        create_configured_app({'APP_DATA_DIR': str(tmp_path), 'API_TOKEN': 'a-long-test-token', 'API_USER': 'alice', 'GRAPH_REPOSITORY': 'typo'})


def test_server_factory_uses_environment(tmp_path, monkeypatch):
    monkeypatch.setenv('APP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('API_TOKEN', 'sample-token')
    monkeypatch.setenv('API_USER', 'alice')
    monkeypatch.setenv('GRAPH_REPOSITORY', 'memory')
    assert create_from_environment() is not None


def test_neo4j_startup_initializes_query_indexes(tmp_path, monkeypatch):
    from unittest.mock import MagicMock
    driver = MagicMock()
    monkeypatch.setattr('backend.app.config.GraphDatabase.driver', lambda *args, **kwargs: driver)
    create_configured_app({'API_TOKEN': 'test-token', 'API_USER': 'alice', 'APP_DATA_DIR': str(tmp_path),
                           'GRAPH_REPOSITORY': 'neo4j', 'NEO4J_URI': 'bolt://localhost:7687',
                           'NEO4J_USER': 'neo4j', 'NEO4J_PASSWORD': 'test-password'})
    assert any('CONSTRAINT' in str(call.args[0]) for call in driver.execute_query.call_args_list)
