from copy import deepcopy
from typing import Protocol


class GraphRepository(Protocol):
    def put_person(self, task: str, person: str, properties: dict) -> None: ...
    def get_person(self, task: str, person: str) -> dict | None: ...
    def list_persons(self, task: str) -> list[dict]: ...
    def delete_person(self, task: str, person: str) -> None: ...
    def put_relation(self, task: str, source: str, target: str, properties: dict) -> None: ...
    def list_relations(self, task: str) -> list[dict]: ...
    def delete_relation(self, task: str, source: str, target: str) -> None: ...


class InMemoryGraphRepository:
    def __init__(self):
        self.people = {}
        self.relations = {}

    def put_person(self, task, person, properties):
        self.people[task, person] = {**deepcopy(properties), 'person_id': person, 'task_id': task}

    def get_person(self, task, person):
        return deepcopy(self.people.get((task, person)))

    def list_persons(self, task):
        return deepcopy([p for (t, _), p in self.people.items() if t == task])

    def delete_person(self, task, person):
        self.people.pop((task, person), None)
        for key in list(self.relations):
            if key[0] == task and person in key[1:]:
                del self.relations[key]

    def put_relation(self, task, source, target, properties):
        if source == target or (task, source) not in self.people or (task, target) not in self.people:
            raise ValueError('distinct existing people required')
        self.relations[task, source, target] = {**deepcopy(properties), 'task_id': task, 'source': source, 'target': target}

    def list_relations(self, task):
        return deepcopy([r for (t, _, _), r in self.relations.items() if t == task])

    def delete_relation(self, task, source, target):
        self.relations.pop((task, source, target), None)


class Neo4jRepository:
    def __init__(self, driver, database='neo4j'):
        self.driver = driver
        self.database = database

    def put_person(self, task, person, properties):
        clean = {k: v for k, v in properties.items() if k not in ('task_id', 'person_id')}
        self.driver.execute_query('MERGE (p:PersonAnon {task_id: $task, person_id: $person}) SET p += $properties', task=task, person=person, properties=clean, database_=self.database)

    def get_person(self, task, person):
        records, _, _ = self.driver.execute_query('MATCH (p:PersonAnon {task_id: $task, person_id: $person}) RETURN properties(p) AS person', task=task, person=person, database_=self.database)
        return dict(records[0]['person']) if records else None

    def list_persons(self, task):
        records, _, _ = self.driver.execute_query('MATCH (p:PersonAnon {task_id: $task}) RETURN properties(p) AS person ORDER BY p.person_id', task=task, database_=self.database)
        return [dict(r['person']) for r in records]

    def delete_person(self, task, person):
        self.driver.execute_query('MATCH (p:PersonAnon {task_id: $task, person_id: $person}) DETACH DELETE p', task=task, person=person, database_=self.database)

    def put_relation(self, task, source, target, properties):
        if source == target:
            raise ValueError('distinct existing people required')
        clean = {k: v for k, v in properties.items() if k not in ('task_id', 'source', 'target')}
        records, _, _ = self.driver.execute_query('MATCH (a:PersonAnon {task_id: $task, person_id: $source}), (b:PersonAnon {task_id: $task, person_id: $target}) MERGE (a)-[r:INFERRED_RELATION {task_id: $task}]->(b) SET r += $properties RETURN properties(r) AS relation', task=task, source=source, target=target, properties=clean, database_=self.database)
        if not records:
            raise ValueError('distinct existing people required')

    def list_relations(self, task):
        records, _, _ = self.driver.execute_query('MATCH (a:PersonAnon {task_id: $task})-[r:INFERRED_RELATION {task_id: $task}]->(b:PersonAnon {task_id: $task}) RETURN properties(r) + {source: a.person_id, target: b.person_id} AS relation ORDER BY a.person_id, b.person_id', task=task, database_=self.database)
        return [dict(r['relation']) for r in records]

    def delete_relation(self, task, source, target):
        self.driver.execute_query('MATCH (a:PersonAnon {task_id: $task, person_id: $source})-[r:INFERRED_RELATION {task_id: $task}]->(b:PersonAnon {task_id: $task, person_id: $target}) DELETE r', task=task, source=source, target=target, database_=self.database)
