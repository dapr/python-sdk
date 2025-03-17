# Example - Conversation API

## Step

### Prepare

- Dapr installed

### Run Conversation Example

<!-- STEP
name: Run Conversation
expected_stdout_lines:
  - "== APP == Result: What's Dapr?"
  - "== APP == Result: Give a brief overview."
background: true
timeout_seconds: 60
-->

```bash
dapr run --app-id conversation \
         --log-level debug \
         --resources-path ./config \
         -- python3 conversation.py
```

<!-- END_STEP -->

## Result

```
  - '== APP == Result: What's Dapr?'
  - '== APP == Result: Give a brief overview.'
```