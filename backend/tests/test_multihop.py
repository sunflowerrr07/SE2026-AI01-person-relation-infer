from time import perf_counter
from unittest.mock import MagicMock
import pytest
from backend.app.repositories import InMemoryGraphRepository, Neo4jRepository


def test_multihop_uses_minimum_distance_and_respects_task_and_depth():
    repo = InMemoryGraphRepository()
    for task in ('T1', 'T2'):
        for person in ('A', 'B', 'C', 'D'):
            repo.put_person(task, person, {})
    for source, target in [('A', 'B'), ('B', 'C'), ('C', 'A'), ('C', 'D')]:
        repo.put_relation('T1', source, target, {})
    repo.put_relation('T2', 'A', 'D', {})
    assert repo.neighbors('T1', 'A', 1) == [{'person_id': 'B', 'hops': 1}, {'person_id': 'C', 'hops': 1}]
    assert repo.neighbors('T1', 'A', 2)[-1] == {'person_id': 'D', 'hops': 2}
    assert repo.neighbors('T1', 'A', 2, 1) == [{'person_id': 'B', 'hops': 1}]
    repo.delete_relation('T1', 'A', 'B')
    assert repo.neighbors('T1', 'A', 1) == [{'person_id': 'C', 'hops': 1}]
    repo.delete_person('T1', 'C')
    assert repo.neighbors('T1', 'A') == []


@pytest.mark.parametrize('hops,limit', [(0, 1), (5, 1), (2, 0), (2, 1001), (1.5, 10), (True, 10)])
def test_multihop_rejects_unbounded_queries(hops, limit):
    with pytest.raises(ValueError):
        InMemoryGraphRepository().neighbors('T', 'P', hops, limit)


def test_missing_source_is_distinct_from_empty_neighborhood():
    with pytest.raises(KeyError):
        InMemoryGraphRepository().neighbors('T', 'missing')


def test_indexed_memory_queries_complete_below_one_second():
    repo = InMemoryGraphRepository()
    for i in range(5000):
        repo.put_person('T', str(i), {})
    for i in range(4999):
        repo.put_relation('T', str(i), str(i + 1), {})
    timings = []
    for _ in range(20):
        start = perf_counter()
        assert len(repo.neighbors('T', '2500', max_hops=4)) == 8
        timings.append(perf_counter() - start)
    assert max(timings) < 1


def test_neo4j_multihop_has_indexes_scope_depth_limit_and_timeout():
    driver = MagicMock()
    repo = Neo4jRepository(driver)
    repo.ensure_schema()
    queries = [str(c.args[0]) for c in driver.execute_query.call_args_list]
    assert any('CONSTRAINT' in q and 'task_id' in q and 'person_id' in q for q in queries)
    session = driver.session.return_value.__enter__.return_value
    session.run.return_value.data.return_value = [{'person_id': 'B', 'hops': 1}]
    assert repo.neighbors('T', 'A', 3, 10) == [{'person_id': 'B', 'hops': 1}]
    query = session.run.call_args.args[0]
    assert '*1..3' in query.text
    assert 'nodes(p)' in query.text and 'relationships(p)' in query.text
    assert 'LIMIT $limit' in query.text
    assert query.timeout < 1
    assert session.run.call_args.kwargs['task'] == 'T'
    assert session.run.call_args.kwargs['person'] == 'A'
    assert session.run.call_args.kwargs['limit'] == 10
    with pytest.raises(ValueError):
        repo.neighbors('T', 'A', 100)
