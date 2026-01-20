---
name: cycle
description: Execute a single cycle test on the kettle controller
---

Run a single test cycle via DoCommand:

```bash
make test-cycle
```

This triggers the `execute_cycle` command on the cycle-tester service, which moves the arm from resting → pour-prep → pause → resting.
