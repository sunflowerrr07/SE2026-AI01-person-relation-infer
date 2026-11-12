import hmac
import sqlite3
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from neo4j.exceptions import ServiceUnavailable, SessionExpired, Neo4jError

from .audit import PersistentAuditLog


class TaskInput(BaseModel):
    media_id: str = Field(min_length=1, max_length=128)


class GraphInput(BaseModel):
    task_id: str = Field(min_length=1, max_length=128)
    properties: dict = Field(default_factory=dict)


def create_app(*, repository, audit_path, task_path, tokens):
    app = FastAPI()
    audit = PersistentAuditLog(audit_path)
    with sqlite3.connect(task_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, owner TEXT NOT NULL, media_id TEXT NOT NULL, status TEXT NOT NULL)')

    def envelope(request, data, code=0):
        return {'request_id': request.state.request_id, 'code': code, 'data': data}

    @app.middleware('http')
    async def audit_request(request: Request, call_next):
        request.state.request_id = uuid4().hex
        request.state.actor = 'anonymous'
        response = await call_next(request)
        audit.record(actor=request.state.actor, action=request.method, target=request.url.path,
                     outcome='denied' if response.status_code in (401, 403) else ('success' if response.status_code < 400 else 'error'),
                     details={'status': response.status_code, 'request_id': request.state.request_id})
        response.headers['X-Request-ID'] = request.state.request_id
        return response

    @app.exception_handler(HTTPException)
    async def handle_http(request, exc):
        return JSONResponse(status_code=exc.status_code, content=envelope(request, None, exc.status_code * 100 + 1))

    @app.exception_handler(ServiceUnavailable)
    @app.exception_handler(SessionExpired)
    async def handle_database_unavailable(request, exc):
        return JSONResponse(status_code=503, content=envelope(request, None, 50301))

    @app.exception_handler(Neo4jError)
    async def handle_database_error(request, exc):
        status = 504 if 'TransactionTimedOut' in (exc.code or '') else 503
        return JSONResponse(status_code=status, content=envelope(request, None, status * 100 + 1))

    def principal(request: Request, authorization: str = Header(default='')):
        prefix = 'Bearer '
        supplied = authorization[len(prefix):] if authorization.startswith(prefix) else ''
        match = next((value for key, value in tokens.items() if supplied and hmac.compare_digest(key, supplied)), None)
        if not match:
            raise HTTPException(401)
        request.state.actor = match[0]
        return match

    def role(user, allowed):
        if user[1] not in allowed:
            raise HTTPException(403)

    def task_row(task_id, user):
        with sqlite3.connect(task_path) as db:
            row = db.execute('SELECT id, owner, media_id, status FROM tasks WHERE id = ?', (task_id,)).fetchone()
        if not row:
            raise HTTPException(404)
        if row[1] != user[0] and user[1] != 'admin':
            raise HTTPException(403)
        return dict(zip(('task_id', 'owner', 'media_id', 'status'), row))

    @app.get('/health')
    def health(request: Request):
        return envelope(request, {'status': 'ok'})

    @app.post('/api/v1/tasks/analyze', status_code=201)
    def create_task(body: TaskInput, request: Request, user=Depends(principal)):
        role(user, {'analyst', 'admin'})
        task = uuid4().hex
        with sqlite3.connect(task_path) as db:
            db.execute('INSERT INTO tasks VALUES (?, ?, ?, ?)', (task, user[0], body.media_id, 'queued'))
        return envelope(request, task_row(task, user))

    @app.get('/api/v1/tasks/{task_id}')
    def get_task(task_id: str, request: Request, user=Depends(principal)):
        return envelope(request, task_row(task_id, user))

    def transition(task_id, user, before, after):
        task_row(task_id, user)
        with sqlite3.connect(task_path) as db:
            cursor = db.execute('UPDATE tasks SET status = ? WHERE id = ? AND status = ?', (after, task_id, before))
            if cursor.rowcount != 1:
                raise HTTPException(409)
        return task_row(task_id, user)

    @app.post('/api/v1/tasks/{task_id}/cancel')
    def cancel(task_id: str, request: Request, user=Depends(principal)):
        return envelope(request, transition(task_id, user, 'queued', 'cancelled'))

    @app.post('/api/v1/tasks/{task_id}/retry')
    def retry(task_id: str, request: Request, user=Depends(principal)):
        return envelope(request, transition(task_id, user, 'cancelled', 'queued'))

    def graph_access(task_id, user):
        role(user, {'analyst', 'admin'})
        task_row(task_id, user)

    def safe_properties(properties, allowed):
        return {key: value for key, value in properties.items() if key in allowed and isinstance(value, (str, int, float, bool))}

    @app.put('/api/v1/graph/persons/{person_id}')
    def put_person(person_id: str, body: GraphInput, request: Request, user=Depends(principal)):
        graph_access(body.task_id, user)
        repository.put_person(body.task_id, person_id, safe_properties(body.properties, {'version', 'first_seen', 'last_seen'}))
        return envelope(request, repository.get_person(body.task_id, person_id))

    @app.get('/api/v1/graph/persons')
    def persons(task_id: str, request: Request, user=Depends(principal)):
        graph_access(task_id, user)
        return envelope(request, repository.list_persons(task_id))

    @app.get('/api/v1/graph/persons/{person_id}/neighbors')
    def neighbors(person_id: str, task_id: str, request: Request, max_hops: int = Query(2, ge=1, le=4), limit: int = Query(100, ge=1, le=1000), user=Depends(principal)):
        graph_access(task_id, user)
        try:
            result = repository.neighbors(task_id, person_id, max_hops, limit)
        except KeyError:
            raise HTTPException(404)
        return envelope(request, result)

    @app.delete('/api/v1/graph/persons/{person_id}')
    def delete_person(person_id: str, task_id: str, request: Request, user=Depends(principal)):
        graph_access(task_id, user)
        repository.delete_person(task_id, person_id)
        return envelope(request, None)

    @app.put('/api/v1/graph/relations/{source}/{target}')
    def put_relation(source: str, target: str, body: GraphInput, request: Request, user=Depends(principal)):
        graph_access(body.task_id, user)
        try:
            repository.put_relation(body.task_id, source, target, safe_properties(body.properties, {'strength', 'confidence', 'category', 'model_version'}))
        except ValueError:
            raise HTTPException(422)
        return envelope(request, None)

    @app.get('/api/v1/graph/relations')
    def relations(task_id: str, request: Request, user=Depends(principal)):
        graph_access(task_id, user)
        return envelope(request, repository.list_relations(task_id))

    @app.delete('/api/v1/graph/relations/{source}/{target}')
    def delete_relation(source: str, target: str, task_id: str, request: Request, user=Depends(principal)):
        graph_access(task_id, user)
        repository.delete_relation(task_id, source, target)
        return envelope(request, None)

    @app.get('/api/v1/audit/events')
    def audit_events(request: Request, user=Depends(principal)):
        role(user, {'admin', 'auditor'})
        return envelope(request, audit.events())

    return app
