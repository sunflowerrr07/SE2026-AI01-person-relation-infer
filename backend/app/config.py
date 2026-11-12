from pathlib import Path
import os
from neo4j import GraphDatabase
from .main import create_app
from .repositories import InMemoryGraphRepository, Neo4jRepository


def create_from_environment():
    return create_configured_app(os.environ)


def create_configured_app(environ):
    token = environ.get('API_TOKEN', '')
    user = environ.get('API_USER', '')
    if not token or not user:
        raise ValueError('API_TOKEN and API_USER are required')
    mode = environ.get('GRAPH_REPOSITORY', 'memory')
    if mode == 'memory':
        repository = InMemoryGraphRepository()
    elif mode == 'neo4j':
        uri, username, password = (environ.get(k) for k in ('NEO4J_URI', 'NEO4J_USER', 'NEO4J_PASSWORD'))
        if not all((uri, username, password)):
            raise ValueError('Neo4j configuration is incomplete')
        driver = GraphDatabase.driver(uri, auth=(username, password))
        driver.verify_connectivity()
        repository = Neo4jRepository(driver, environ.get('NEO4J_DATABASE', 'neo4j'))
    else:
        raise ValueError('unknown graph repository')
    directory = Path(environ.get('APP_DATA_DIR', 'data'))
    directory.mkdir(parents=True, exist_ok=True)
    return create_app(repository=repository, audit_path=directory / 'audit.sqlite3', task_path=directory / 'tasks.sqlite3', tokens={token: (user, environ.get('API_ROLE', 'analyst'))})
