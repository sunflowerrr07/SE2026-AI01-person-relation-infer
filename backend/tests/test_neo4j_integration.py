import os
from uuid import uuid4
import pytest
from neo4j import GraphDatabase
from backend.app.repositories import Neo4jRepository


@pytest.mark.integration
def test_neo4j_graph_round_trip():
    uri = os.environ.get('TEST_NEO4J_URI')
    user = os.environ.get('TEST_NEO4J_USER')
    password = os.environ.get('TEST_NEO4J_PASSWORD')
    if not all((uri, user, password)):
        pytest.skip('TEST_NEO4J_URI, TEST_NEO4J_USER and TEST_NEO4J_PASSWORD are required')
    task = 'test-' + uuid4().hex
    with GraphDatabase.driver(uri, auth=(user, password)) as driver:
        repo = Neo4jRepository(driver, os.environ.get('TEST_NEO4J_DATABASE', 'neo4j'))
        try:
            repo.put_person(task, 'P1', {'version': 1})
            repo.put_person(task, 'P2', {'version': 1})
            assert repo.get_person(task, 'P1')['version'] == 1
            repo.put_relation(task, 'P1', 'P2', {'strength': 0.5})
            assert repo.list_relations(task)[0]['strength'] == 0.5
            repo.delete_relation(task, 'P1', 'P2')
            assert repo.list_relations(task) == []
        finally:
            repo.delete_person(task, 'P1')
            repo.delete_person(task, 'P2')
