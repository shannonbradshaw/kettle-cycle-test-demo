---
name: reload
description: Hot-reload the module to the connected machine
---

Rebuild and hot-reload the module:

```bash
make reload-module
```

This:
1. Removes existing build artifacts
2. Rebuilds the binary for the target platform (linux/arm64 for Raspberry Pi)
3. Packages it into module.tar.gz
4. Uploads and restarts the module on the machine via `viam module reload-local`
