from copy import deepcopy
from datetime import datetime, timezone
import json
import sqlite3
from .privacy import redact


class AuditLog:
    def __init__(self):
        self._events = []

    def record(self, *, actor, action, target, outcome, details):
        self._events.append({'actor': actor, 'action': action, 'target': target,
                             'outcome': outcome, 'details': redact(details),
                             'timestamp': datetime.now(timezone.utc).isoformat()})

    def events(self):
        return deepcopy(self._events)


class PersistentAuditLog:
    def __init__(self, path):
        self.path = str(path)
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY, event TEXT NOT NULL)')

    def record(self, *, actor, action, target, outcome, details):
        event = {'actor': actor, 'action': action, 'target': target, 'outcome': outcome,
                 'details': redact(details), 'timestamp': datetime.now(timezone.utc).isoformat()}
        with sqlite3.connect(self.path) as db:
            db.execute('INSERT INTO audit(event) VALUES (?)', (json.dumps(event, ensure_ascii=False),))

    def events(self):
        with sqlite3.connect(self.path) as db:
            return [json.loads(row[0]) for row in db.execute('SELECT event FROM audit ORDER BY id')]
