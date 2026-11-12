from backend.app.privacy import anonymize, redact


def test_anonymize_generates_distinct_non_identifying_ids():
    first = anonymize()
    second = anonymize()
    assert first.startswith('PA-')
    assert first != second


def test_redact_removes_sensitive_fields_recursively():
    assert redact({'name': 'Alice', 'nested': [{'password': 'secret', 'task_id': 'T1'}]}) == {
        'nested': [{'task_id': 'T1'}]
    }
