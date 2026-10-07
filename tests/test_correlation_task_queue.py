"""AIP TaskQueue event contract (aip/tasks.py:_append_task_event)."""
from imx.correlation import correlate_events
import pytest


@pytest.mark.parametrize('stage,outcome', [('done', 'succeeded'), ('failed', 'failed')])
def test_native_task_queue_terminal_outcome(stage, outcome):
    events = [
        {'event': 'task', 'task_id': 'queue-1', 'agent': 'script-worker',
         'ts': '2026-10-02T00:00:00Z', 'action': 'create', 'stage': 'pending'},
        {'event': 'task', 'task_id': 'queue-1', 'agent': 'script-worker',
         'ts': '2026-10-02T00:00:01Z', 'action': 'claim', 'stage': 'claimed'},
        {'event': 'task', 'task_id': 'queue-1', 'agent': 'script-worker',
         'ts': '2026-10-02T00:00:02Z', 'action': stage, 'stage': stage},
    ]
    decisions = [{'task_id': 'queue-1', 'node_id': 'local-script',
                  'task_class': 'integration.correlation'}]
    records = correlate_events(events, decisions)
    assert len(records) == 1
    assert records[0]['outcome'] == outcome
    assert records[0]['agent'] == 'script-worker'
    assert records[0]['missing_fields'] == []
    assert records[0]['duration_ms'] == 2000


@pytest.mark.parametrize('stage,expected', [('failed', 'failed'), ('done', 'succeeded'), ('claimed', 'unknown'), ('pending', 'unknown')])
def test_queue_stage_is_authoritative_over_agent_status(stage, expected):
    events = [
        {'event': 'task', 'task_id': 't1', 'stage': 'failed', 'ts': '1'},
        {'event': 'task', 'task_id': 't1', 'stage': stage, 'ts': '2'},
        {'event': 'status', 'task': 't1', 'status': 'finished', 'ts': '3'},
    ]
    assert correlate_events(events, [])[0]['outcome'] == expected
