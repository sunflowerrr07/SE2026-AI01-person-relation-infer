from backend.app.audit import AuditLog, PersistentAuditLog


def test_audit_records_result_without_secrets():
    audit = AuditLog()
    audit.record(actor='analyst', action='query', target='T1', outcome='denied', details={'token': 'secret', 'reason': 'forbidden'})
    events = audit.events()
    assert events[0]['actor'] == 'analyst'
    assert events[0]['outcome'] == 'denied'
    assert events[0]['details'] == {'reason': 'forbidden'}
    events[0]['outcome'] = 'success'
    assert audit.events()[0]['outcome'] == 'denied'


def test_audit_survives_reopening_and_redacts_secrets(tmp_path):
    path = tmp_path / 'audit.sqlite3'
    log = PersistentAuditLog(path)
    log.record(actor='u1', action='read', target='T1', outcome='denied', details={'password': 'secret', 'reason': 'denied'})
    events = PersistentAuditLog(path).events()
    assert len(events) == 1
    assert events[0]['details'] == {'reason': 'denied'}
    assert events[0]['outcome'] == 'denied'
