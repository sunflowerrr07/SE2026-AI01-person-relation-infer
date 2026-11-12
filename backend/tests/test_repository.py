import pytest
from backend.app.repositories import InMemoryGraphRepository


@pytest.fixture
def repo():
    return InMemoryGraphRepository()


def test_person_crud_scoped_to_task(repo):
    repo.put_person('T1', 'P1', {'version': 1})
    repo.put_person('T1', 'P1', {'version': 2})
    assert repo.get_person('T1', 'P1')['version'] == 2
    assert repo.get_person('T2', 'P1') is None
    assert len(repo.list_persons('T1')) == 1
    repo.delete_person('T1', 'P1')
    assert repo.get_person('T1', 'P1') is None


def test_relation_crud_and_cascade(repo):
    repo.put_person('T1', 'P1', {})
    repo.put_person('T1', 'P2', {})
    repo.put_relation('T1', 'P1', 'P2', {'strength': 0.4})
    repo.put_relation('T1', 'P1', 'P2', {'strength': 0.7})
    assert repo.list_relations('T1')[0]['strength'] == 0.7
    assert repo.list_relations('T2') == []
    repo.delete_person('T1', 'P1')
    assert repo.list_relations('T1') == []


def test_relation_requires_distinct_existing_people(repo):
    repo.put_person('T1', 'P1', {})
    with pytest.raises(ValueError):
        repo.put_relation('T1', 'P1', 'P1', {})
    with pytest.raises(ValueError):
        repo.put_relation('T1', 'P1', 'missing', {})


def test_delete_relation_is_idempotent(repo):
    repo.put_person('T1', 'P1', {})
    repo.put_person('T1', 'P2', {})
    repo.put_relation('T1', 'P1', 'P2', {})
    repo.delete_relation('T1', 'P1', 'P2')
    repo.delete_relation('T1', 'P1', 'P2')
    assert repo.list_relations('T1') == []
