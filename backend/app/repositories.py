from copy import deepcopy
from typing import Protocol
from collections import defaultdict
from neo4j import Query


def validate_query_bounds(max_hops, limit):
    if type(max_hops) is not int or not 1 <= max_hops <= 4 or type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError('max_hops must be 1..4 and limit must be 1..1000')


class GraphRepository(Protocol):
    def neighbors(self, task: str, person: str, max_hops: int = 2, limit: int = 100) -> list[dict]: ...
    def put_person(self, task: str, person: str, properties: dict) -> None: ...
    def get_person(self, task: str, person: str) -> dict | None: ...
    def list_persons(self, task: str) -> list[dict]: ...
    def delete_person(self, task: str, person: str) -> None: ...
    def put_relation(self, task: str, source: str, target: str, properties: dict) -> None: ...
    def list_relations(self, task: str) -> list[dict]: ...
    def delete_relation(self, task: str, source: str, target: str) -> None: ...


class InMemoryGraphRepository:
    def neighbors(self, task, person, max_hops=2, limit=100):
        validate_query_bounds(max_hops, limit)
        if (task, person) not in self.people:
            raise KeyError(person)
        visited, frontier, result = {person}, {person}, []
        for hops in range(1, max_hops + 1):
            following = set()
            for current in frontier:
                following.update(self.adjacency.get((task, current), set()))
            following.difference_update(visited)
            for identifier in sorted(following):
                result.append({'person_id': identifier, 'hops': hops})
                if len(result) == limit:
                    return result
            visited.update(following)
            frontier = following
            if not frontier:
                break
        return result

    def __init__(self):
        self.people = {}
        self.relations = {}
        self.adjacency = defaultdict(set)

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
                self.delete_relation(*key)
        self.adjacency.pop((task, person), None)

    def put_relation(self, task, source, target, properties):
        if source == target or (task, source) not in self.people or (task, target) not in self.people:
            raise ValueError('distinct existing people required')
        self.relations[task, source, target] = {**deepcopy(properties), 'task_id': task, 'source': source, 'target': target}
        self.adjacency[task, source].add(target)
        self.adjacency[task, target].add(source)

    def list_relations(self, task):
        return deepcopy([r for (t, _, _), r in self.relations.items() if t == task])

    def delete_relation(self, task, source, target):
        self.relations.pop((task, source, target), None)
        if (task, target, source) not in self.relations:
            self.adjacency[task, source].discard(target)
            self.adjacency[task, target].discard(source)


class Neo4jRepository:
    def ensure_schema(self):
        self.driver.execute_query('CREATE CONSTRAINT person_task_unique IF NOT EXISTS FOR (p:PersonAnon) REQUIRE (p.task_id, p.person_id) IS UNIQUE', database_=self.database)
        self.driver.execute_query('CREATE INDEX inferred_relation_task IF NOT EXISTS FOR ()-[r:INFERRED_RELATION]-() ON (r.task_id)', database_=self.database)

    def neighbors(self, task, person, max_hops=2, limit=100):
        validate_query_bounds(max_hops, limit)
        # Only the validated integer depth enters query text; all data is parameterized.
        query = Query(f'''MATCH (s:PersonAnon {{task_id: $task, person_id: $person}})
            OPTIONAL MATCH p=(s)-[:INFERRED_RELATION*1..{max_hops}]-(n:PersonAnon)
            WHERE n <> s AND all(node IN nodes(p) WHERE node.task_id = $task)
              AND all(edge IN relationships(p) WHERE edge.task_id = $task)
            WITH n, min(length(p)) AS hops
            RETURN n.person_id AS person_id, hops ORDER BY hops, person_id LIMIT $limit''', timeout=0.8)
        # Auto-commit query avoids managed-transaction retries extending the latency budget.
        with self.driver.session(database=self.database, default_access_mode='READ') as session:
            records = session.run(query, task=task, person=person, limit=limit).data()
        if not records:
            raise KeyError(person)
        return [dict(person_id=r['person_id'], hops=r['hops']) for r in records if r['person_id'] is not None]

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
        records, _, _ = self.driver.execute_query('MATCH (a:PersonAnon {task_id: $task})-[r:INFERRED_RELATION {task_id: $task}]->(b:PersonAnon {task_id: $task}) RETURN properties(r) AS relation, a.person_id AS source, b.person_id AS target ORDER BY a.person_id, b.person_id', task=task, database_=self.database)
        return [{**dict(r['relation']), 'source': r['source'], 'target': r['target']} for r in records]

    def delete_relation(self, task, source, target):
        self.driver.execute_query('MATCH (a:PersonAnon {task_id: $task, person_id: $source})-[r:INFERRED_RELATION {task_id: $task}]->(b:PersonAnon {task_id: $task, person_id: $target}) DELETE r', task=task, source=source, target=target, database_=self.database)
