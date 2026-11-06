import pytest

EXPECTED_FRAUD_REMEDIATION = [
    '*** Lakeflow micro-batch 1: scheduling fraud remediation workflows',
    'dapr.ext.databricks: sink=fraud_actions workflow=fraud_remediation instance_id=fraud-fraud_actions-v1-T-1001 batch_id=1 namespace=fraud generation=v1 outcome=newly_scheduled',
    'dapr.ext.databricks: sink=fraud_actions workflow=fraud_remediation instance_id=fraud-fraud_actions-v1-T-1002 batch_id=1 namespace=fraud generation=v1 outcome=newly_scheduled',
    '*** Micro-batch 1 handed off; each workflow now runs independently',
    '*** Simulating a Lakeflow retry of the same micro-batch',
    'dapr.ext.databricks: sink=fraud_actions workflow=fraud_remediation instance_id=fraud-fraud_actions-v1-T-1001 batch_id=1 namespace=fraud generation=v1 outcome=already_existed',
    'dapr.ext.databricks: sink=fraud_actions workflow=fraud_remediation instance_id=fraud-fraud_actions-v1-T-1002 batch_id=1 namespace=fraud generation=v1 outcome=already_existed',
    '*** Retry complete: no duplicate workflow executions were created',
    '*** Freezing card for transaction T-1001 (customer C-1)',
    '*** Freezing card for transaction T-1002 (customer C-2)',
    '*** Notifying customer C-1 about the frozen card',
    '*** Notifying customer C-2 about the frozen card',
    '*** Opened investigation CASE-T-1001',
    '*** Opened investigation CASE-T-1002',
    '*** Resolved CASE-T-1001: CONFIRMED_FRAUD',
    '*** Resolved CASE-T-1002: CONFIRMED_FRAUD',
    '*** Workflow fraud-fraud_actions-v1-T-1001 completed: {"case_id": "CASE-T-1001", "decision": "CONFIRMED_FRAUD"}',
    '*** Workflow fraud-fraud_actions-v1-T-1002 completed: {"case_id": "CASE-T-1002", "decision": "CONFIRMED_FRAUD"}',
]


@pytest.mark.example_dir('databricks')
def test_fraud_remediation_workflow(dapr):
    output = dapr.run(
        '--app-id fraud-remediation-demo -- python3 fraud_remediation_workflow.py',
        timeout=60,
    )
    for line in EXPECTED_FRAUD_REMEDIATION:
        assert line in output, f'Missing in output: {line}'

    # The whole point of the sink is to schedule-and-move-on: scheduling must
    # never be reported as newly_scheduled a second time for the retried batch.
    assert output.count('outcome=newly_scheduled') == 2
    assert output.count('outcome=already_existed') == 2
