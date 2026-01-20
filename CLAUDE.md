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
Milestone 2 complete. Arm moves between saved positions via position-saver switches on command.

*(Keep this updated whenever a project phase or milestone advances.)*

## Open Questions
- How will we detect a real break? (mechanical design)
- How will we fake a break for testing? (removable patch concept)

# Implementation Notes
- Use `LinearConstraint` for level kettle movement; highlight in README as Viam feature
- Simple tilt-and-return pour for milestones; graceful arc motion is bonus round
- Mock vision service allows alerting development before CV model is trained
- Training mode tags images for dataset collection without acting on inference results
- Position-saver switches (vmodutils) trigger arm movements; arm is explicit dependency for clarity in service dependency chain
- `execute_cycle` moves: resting → pour_prep → pause (1s) → resting 

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


## Project Commands

### Viam CLI
- `viam machine part run --part <part_id> --method <method> --data '{}'` — run commands against the machine
- `viam machine part run --part <part_id> --component <name> --method DoCommand --data '{}'` — call DoCommand on a component/service
- `viam machine logs --machine <machine_id> --count 20 --keyword <filter>` — view machine logs (machine_id from machine.json)
- `viam organizations list` — list orgs and their namespaces
- Machine config stored in `machine.json`

### Development Commands
- `go test ./...` — run all unit tests
- `make module.tar.gz` — build packaged module
- `make reload-module` — hot-reload module to robot (uses PART_ID from machine.json)
- `make test-cycle` — trigger execute_cycle DoCommand via CLI

### Module Generation
```bash
viam module generate \
  --language go \
  --name kettle-cycle-test \
  --public-namespace viamdemo \
  --model-name controller \
  --resource-subtype generic-service \
  --visibility private
```
- Use `generic-service` for logic/orchestration, `generic-component` for hardware
- `--public-namespace` must match your Viam org's namespace

### Hot Reload Deployment
```bash
viam module reload-local --part-id <part_id from machine.json>
```
Builds, packages, uploads via shell service, and restarts the module on the target machine.

### TODO: Machine Config Sync
Create a CLI tool/script to pull current machine config from Viam and store in repo, so machine construction is captured in version control.

## Development Workflow

### Starting Work
1. Create a feature branch: `git checkout -b feature/<milestone-or-feature-name>`
2. Never commit directly to main

### Writing Tests
1. Write tests
2. Run `test-scrutinizer` agent to review for quality and meaningful coverage
3. Present tests to user for approval
4. Run tests and get user's sign-off
5. Implement feature

### Before Committing
The pre-commit hook (`.claude/hooks/pre-commit.md`) automates:
1. Running tests
2. Running docs-updater agent
3. Running changelog-updater agent
4. Staging doc changes

Just commit — the hook handles the rest.

### Completing Work
1. Merge branch to main (solo) or open PR (collaborative)
2. Use `retro-reviewer` agent to review Claude Code usage and suggest workflow improvements

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

