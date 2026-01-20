# Kettle Cycle Testing Demo Project

## Project Planning

1. Answer all project planning questions with a conversation or a research report
2. Establish data schema within Viam's framework of data sync
3. Finalize concept and outline for README
4. Set up claude agents
    - Docs updating agent with specific instructions for README
    - Changelog
    - Test scrutinizer
    - Retro agent to help me tune my use of claude code features (claude.md, agents, slash commands)
5. Set up any .env stuff (probably zero but check). Ask Claude for a template that takes my stack into account.
6. Develop
7. Publish module publicly

### Current Milestone
Milestone 4 complete. Force sensor captures load cell data during put-down phase via DoCommand coordination pattern.

*(Keep this updated whenever a project phase or milestone advances.)*

## Open Questions
- How will we detect a real break? (mechanical design)
- How will we fake a break for testing? (removable patch concept)

## Technical Debt
- `cycleLoop()` in module.go ignores errors from `handleExecuteCycle()` - should log failures during continuous trials
- Rename `samplingLoop()` in force_sensor.go to have a verb (e.g., `runSamplingLoop()`)
- Investigate selectively disabling data capture polling when not in a trial (vs relying on `should_sync=false`)
- Force sensor requires `load_cell` config but uses mock when `use_mock_curve=true` - consider making mock a virtual sensor for cleaner config

# Implementation Notes
- Use `LinearConstraint` for level kettle movement; highlight in README as Viam feature
- Simple tilt-and-return pour for milestones; graceful arc motion is bonus round
- Mock vision service allows alerting development before CV model is trained
- Training mode tags images for dataset collection without acting on inference results
- Position-saver switches (vmodutils) trigger arm movements; arm is explicit dependency for clarity in service dependency chain
- `execute_cycle` moves: resting → pour_prep → pause (1s) → resting → pause (1s)
- Trial lifecycle: `start` begins continuous cycling in background goroutine, `stop` ends trial and returns count
- Trial-sensor component wraps controller state via `stateProvider` interface for Viam data capture
- `should_sync` field enables conditional data capture (only sync when trial is active)
- Service dependencies work like component dependencies; sensor declares controller as full resource name
- Force sensor wraps `forceReader` interface (mock or sensorForceReader) for hardware abstraction
- Controller calls force sensor's start_capture/end_capture DoCommands, passing trial metadata via parameters
- DoCommand coordination pattern avoids circular dependencies while enabling rich coordination
- Force sensor state machine: idle → waiting (for first non-zero) → active → idle
- `waitForArmStopped()` polls arm.IsMoving() to ensure clean capture timing
- Force sensor returns trial_id/cycle_count from start_capture params, setting should_sync accordingly
- Viam's builder UI sensor test card lets you verify force sensor readings without CLI commands 

## Documentation

- [Project Spec](product_spec.md) - full description of project, specs
- [Changelog](changelog.md)
- [README](README.md) - docs especially crafted for Viam learners with architecture and design documentation.

### README Maintenance

The README has a **target outline** (in product_spec.md) and a **backlog** (below). After each milestone or significant change:

1. Update README sections that can now be written based on implemented code
2. Move completed backlog items into the README
3. Add new backlog items for content that requires future work (e.g., video, screenshots of UI that doesn't exist yet)

**Backlog** (content waiting on future implementation):
- Demo video/gif showing module in action
- Hardware setup section (parts list, wiring diagrams, 3D-printed fixture details)
- Architecture diagram showing component relationships
- Screenshots of Viam app configuration
- Lesson 1 walkthrough content for Milestone 1
- Lesson 2 walkthrough content for Milestone 2 (position-saver switches, arm as explicit dependency)
- Lesson 3 walkthrough content for Milestone 3 (trial lifecycle, sensor wrapping service state, conditional data capture)
- Lesson 4 walkthrough content for Milestone 4 (DoCommand coordination, wrapper component pattern, forceReader abstraction, capture state machine, waitForArmStopped timing)


## Project Commands

### Slash Commands

| Command | Description |
|---------|-------------|
| `/start-feature <name>` | Create and switch to a feature branch |
| `/cycle` | Execute a single test cycle on the arm |
| `/trial-start` | Start continuous trial (background cycling) |
| `/trial-stop` | Stop active trial, return cycle count |
| `/trial-status` | Check trial status and cycle count |
| `/logs [keyword]` | View machine logs (optionally filtered) |
| `/status` | Get machine/component health status |
| `/reload` | Hot-reload module to machine |
| `/gen-module` | Generate new Viam module scaffold |

### Viam CLI

- `viam machine part run --part <part_id> --method <method> --data '{}'` — run commands against the machine
- `viam machine logs --machine <machine_id> --count N` — view machine logs (uses machine_id, not part_id)
- `viam organizations list` — list orgs and their namespaces

**Limitations:** No CLI command to fetch machine config (use Viam app UI). No `--service` flag for generic services (use full gRPC method). See `viam-cli-patterns` skill for details.

### Development Commands
- `go test ./...` — run all unit tests
- `make module.tar.gz` — build packaged module
- `make reload-module` — hot-reload module to robot (uses PART_ID from machine.json)
- `make test-cycle` — trigger execute_cycle DoCommand via CLI
- `make trial-start` — start a trial (continuous cycling)
- `make trial-stop` — stop the active trial
- `make trial-status` — check trial status and cycle count

### Module Generation

Use `/gen-module <subtype> <model_name>` slash command. Tips:
- Use `generic-service` for logic/orchestration, `generic-component` for hardware
- `--public-namespace` must match your Viam org's namespace

### Hot Reload Deployment

Use `/reload` or `make reload-module`. Builds, packages, uploads via shell service, and restarts the module on the target machine.

### TODO: Machine Config Sync
Create a CLI tool/script to pull current machine config from Viam and store in repo, so machine construction is captured in version control.

## Development Workflow

### Starting Work
1. **Run `pre-work-check` agent** — verifies feature branch and passing tests
2. If on main, use `/start-feature <name>` to create branch
3. Never commit directly to main

**Important:** After context compaction, branch state may be lost. Always verify with `pre-work-check` before continuing work.

### Feature Development
Use `/feature-dev` as the primary workflow for non-trivial features. It provides:
- Discovery and clarifying questions
- Agent-driven codebase exploration
- Architecture design with trade-off analysis
- Implementation with quality review

**Project-specific addition after Architecture Design (Phase 4):**
Before implementation, create a test plan using the required template:

| Test Name | Category | Custom Logic Tested |
|-----------|----------|---------------------|
| ... | ... | ... |

Categories: Config validation, Constructor validation, State machine, Thread safety, Error handling, Integration, Documentation

**Test Scrutiny Phase 1:** Delegate to `test-scrutinizer` agent for plan review. The agent will:
- Verify each test names specific custom logic (not SDK/library code)
- Validate categories are accurate (not just accepted at face value)
- Save the approved proposal to `.claude/test-proposals/<branch-name>.md` for Phase 2 comparison

Tests must name specific custom logic being tested — if you can't, it's likely plumbing.

### Implementation Phase (TDD)
1. Write tests according to approved plan
2. Run tests (should fail)
3. Implement feature
4. Run tests (should pass)
5. **Test Scrutiny Phase 2:** Delegate to `test-scrutinizer` agent for implementation review
   - Agent reads saved proposal from `.claude/test-proposals/<branch-name>.md`
   - Compares written tests against proposal
   - Verifies tests actually test what they claimed to test
   - Checks for proper techniques (direct handlers, state verification, direct state setup)
6. **If Phase 2 fails:** Return to step 1 — rewrite tests to match proposal, or revise proposal and re-run Phase 1

### Physical Validation
Before updating docs, verify the feature works on real hardware:
1. Build module: `make module.tar.gz`
2. Deploy to machine: `/reload`
3. Verify in Viam app (sensor test cards, component status)
4. If issues found, fix and re-run unit tests before proceeding

**Why this matters:** Unit tests verify logic, but physical validation catches integration issues (config problems, dependency resolution, hardware timing). Docs should describe working behavior, not theoretical behavior.

### Committing Changes

When asked to commit:
1. Run tests: `go test ./...`
2. If tests fail, abort and report
3. Run `docs-updater` agent
4. Run `changelog-updater` agent
5. Stage doc changes
6. Execute `git commit`

### Completing Work
1. **Delegate to `completion-checker` agent** — verify branch is ready to merge
2. Address any blocking issues
3. Merge branch to main (solo) or open PR (collaborative)
4. Use `retro-reviewer` agent periodically to review Claude Code usage and suggest improvements

## Testing Philosophy

### Test the Right Things at the Right Layers

**Unit tests** — custom logic only:
- State machines (transitions, edge cases)
- Config/constructor validation
- Thread safety of concurrent operations
- Error handling (our handling logic, not that errors propagate)

**Integration tests** — system state at lifecycle boundaries:
- State after start/stop operations
- Correct initialization of compound state
- Multi-component coordination results

**Documentation tests** — prove contracts:
- Wrapper components return exactly what they wrap (e.g., sensor.Readings() == controller.GetState())

### What NOT to Test

| Anti-pattern | Example | Why it's bad |
|--------------|---------|--------------|
| Plumbing | "DoCommand routes to handleStart" | Tests dispatch, not logic |
| Delegation | "sensor.Readings calls controller.GetState" | Tests wiring, not behavior |
| Library code | "switch.SetPosition moves arm" | Trust the SDK |
| Orchestration | "execute_cycle calls switch A then switch B" | Tests sequence, not outcomes |
| Dead code | "GetSamplingPhase returns empty" | If unused, delete it |
| Constants | "defaultTimeout == 10s" | Tautology |

### Testing Techniques

**Direct handler calls** — test handlers directly, not through DoCommand:
```go
// Bad: tests DoCommand dispatch + handler
kctrl.DoCommand(ctx, map[string]interface{}{"command": "start"})

// Good: tests handler logic only
kctrl.handleStart()
```

**State verification over call verification** — verify resulting state, not that calls were made:
```go
// Bad: verify switch was called
assert(mockSwitch.SetPositionCalled)

// Good: verify system state after operation
state := kctrl.GetState()
assert(state["cycle_count"] == 1)
```

**Direct state setup** — set state directly rather than calling code that sets state (unless testing that code):
```go
// Bad: calls handleStart() which spawns goroutine, creating race with our test
kctrl.handleStart()
kctrl.handleExecuteCycle(ctx)
state := kctrl.GetState() // racing with background loop!

// Good: manually set up trial state to test cycle increment in isolation
kctrl.mu.Lock()
kctrl.activeTrial = &trialState{trialID: "test", stopCh: make(chan struct{})}
kctrl.mu.Unlock()
kctrl.handleExecuteCycle(ctx)
state := kctrl.GetState() // no race, testing exactly what we want
```

This isolates the logic under test. If `handleStart()` breaks, a test for `handleStart()` will catch it — not every test that happens to use it.

### Test Proposal Template

When proposing tests during planning, use this format:

| Test Name | Category | Custom Logic Tested |
|-----------|----------|---------------------|
| TestTrial_StartWhileRunning_Errors | State machine | Mutex-protected concurrent start rejection |
| TestForceSensor_BufferRolling | State machine | Ring buffer overflow handling |
| TestTrialSensor_ReadingsMatchesController | Documentation | Wrapper returns identical state to source |

**Categories:**
- `Config validation` — required fields, invalid values
- `Constructor validation` — dependency resolution, initialization errors
- `State machine` — transitions, guards, concurrent access
- `Thread safety` — race conditions under concurrent access
- `Error handling` — our error wrapping/recovery logic
- `Integration` — system state at lifecycle boundaries
- `Documentation` — proves API contracts

The category + custom logic columns implicitly justify the test. If you can't name specific custom logic being tested, the test is likely plumbing.

## Troubleshooting

### Module Won't Register
- **Symptom:** Module uploads but doesn't appear in machine config
- **Fix:** Ensure your org's public namespace is set in Viam app (Settings → Organization)
- **Note:** Namespace in `viam module generate --public-namespace` must match org setting

### Hot Reload Fails
- **Symptom:** `viam module reload-local` hangs or errors
- **Fix:** Check `machine.json` has correct part_id and machine is online

### Service vs Component Mismatch
- **Symptom:** "unknown resource type" error in logs
- **Fix:** Ensure the API in machine config matches the module registration:
  - `rdk:service:generic` → use `generic-service` subtype, `RegisterService()` in code
  - `rdk:component:generic` → use `generic-component` subtype, `RegisterComponent()` in code

### Debugging Workflow

1. **Check if module is healthy:** `/status`
2. **View recent errors:** `/logs error`
3. **Test the cycle:** `/cycle`
4. **View all logs:** `/logs`

## Reference

### Terms

- A complete cycle test for a given specimen is a "trial".
- A single cycle in that trial is a "cycle".

### Benefit notes:

- Using motion to program pouring decouples it from the saved poses and the particulars of the fixture that grips the kettle. 
- machine builder test cards remove need for writing hello world scripts and testing connectivity, even with CV components
- 

### Demo Flow
1. 2-minute Viam architecture overview
2. Build the machine in Viam app from scratch (introduce Viam concepts as we go)
3. Show physical setup, explain components
4. Start cycle routine via job component
5. Run several cycles, show data capture in action
6. Trigger simulated failure (remove patch from handle)
7. CV detects failure, alert fires, cycle stops
8. Show captured data: images, force profiles, event log
9. Show fragment configuration with variable substitution


# Design Guidelines

## Constraints

### Security
- Always run tests before committing
- Always use environment variables for secrets
- Never commit .env.local or any file with API Keys.

