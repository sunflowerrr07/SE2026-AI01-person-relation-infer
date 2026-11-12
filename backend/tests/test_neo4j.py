from unittest.mock import MagicMock
import pytest
from backend.app.repositories import Neo4jRepository


def test_person_crud_uses_parameterized_queries():
    driver = MagicMock()
    repo = Neo4jRepository(driver)
    repo.put_person('task', 'person', {'version': 1})
    query, = driver.execute_query.call_args.args
    args = driver.execute_query.call_args.kwargs
    assert 'MERGE' in query and '$task' in query and '$person' in query
    assert args['task'] == 'task' and args['person'] == 'person'
    assert args['properties'] == {'version': 1}
    driver.execute_query.return_value = ([{'person': {'person_id': 'person', 'task_id': 'task'}}], None, None)
    assert repo.get_person('task', 'person')['person_id'] == 'person'
    assert len(repo.list_persons('task')) == 1
    repo.delete_person('task', 'person')
    assert 'DETACH DELETE' in driver.execute_query.call_args.args[0]


def test_relation_requires_existing_distinct_nodes_and_supports_delete():
    driver = MagicMock()
    repo = Neo4jRepository(driver)
    with pytest.raises(ValueError):
        repo.put_relation('T', 'P', 'P', {})
    driver.execute_query.return_value = ([], None, None)
    with pytest.raises(ValueError):
        repo.put_relation('T', 'P', 'Q', {})
    driver.execute_query.return_value = ([{'relation': {'strength': 0.5}}], None, None)
    repo.put_relation('T', 'P', 'Q', {'strength': 0.5})
    assert repo.list_relations('T')[0]['strength'] == 0.5
    repo.delete_relation('T', 'P', 'Q')
    assert 'DELETE' in driver.execute_query.call_args.args[0]
