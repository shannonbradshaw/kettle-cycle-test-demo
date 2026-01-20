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
Currently in pre-planning, step 6 (Develop).

*(Keep this updated whenever a project phase or milestone advances.)*

## Open Questions
- How will we detect a real break? (mechanical design)
- How will we fake a break for testing? (removable patch concept)

# Implementation Notes
- Use `LinearConstraint` for level kettle movement; highlight in README as Viam feature
- Simple tilt-and-return pour for milestones; graceful arc motion is bonus round
- Mock vision service allows alerting development before CV model is trained
- Training mode tags images for dataset collection without acting on inference results 

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
- *(empty — no code yet)*


## Project Commands

### Viam CLI
- `viam machine part run` — run commands against the machine
- Machine config stored in `machine.json`

### TODO: Machine Config Sync
Create a CLI tool/script to pull current machine config from Viam and store in repo, so machine construction is captured in version control. 

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

