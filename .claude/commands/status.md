---
name: status
description: Get current machine status and component health from Viam
---

Check machine status and component health:

```bash
PART_ID=$(jq -r '.part_id' machine.json)
viam machine part run --part $PART_ID \
  --method 'viam.robot.v1.RobotService.GetMachineStatus' \
  --data '{}'
```

Returns full machine status including component states (STATE_READY, STATE_UNHEALTHY, etc.) and any error messages.
