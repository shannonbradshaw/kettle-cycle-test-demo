---
name: gen-module
description: Generate a new Viam module with project-specific defaults
arguments:
  - name: subtype
    description: Resource subtype (generic-service, generic-component, etc.)
    required: true
  - name: model_name
    description: Model name (e.g., controller, sensor)
    required: true
---

Run the Viam module generator with this project's standard settings:

```bash
viam module generate \
  --language go \
  --name kettle-cycle-test \
  --public-namespace viamdemo \
  --model-name $ARGUMENTS.model_name \
  --resource-subtype $ARGUMENTS.subtype \
  --visibility private
```

After generation:
1. Move generated files from subdirectory to project root if needed
2. Run `go mod tidy`
3. Run tests: `go test ./...`
