---
name: logs
description: View recent machine logs from Viam
arguments:
  - name: keyword
    description: Filter logs by keyword (optional)
    required: false
---

View recent machine logs:

```bash
MACHINE_ID=$(jq -r '.machine_id' machine.json)
{{#if keyword}}
viam machine logs --machine $MACHINE_ID --count 50 --keyword {{keyword}}
{{else}}
viam machine logs --machine $MACHINE_ID --count 50
{{/if}}
```

Shows the 50 most recent log entries from the connected machine.
