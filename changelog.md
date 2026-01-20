# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Milestone 2: Arm Movement Between Saved Positions

**Added**
- `execute_cycle` DoCommand that cycles arm between resting and pour-prep positions
- Config validation for arm, resting_position, and pour_prep_position attributes
- Position-saver switch integration for arm movement control
- `make reload-module` target for hot-reload deployment to robot
- `make test-cycle` target for triggering cycle tests via CLI
- Cross-compilation support for Raspberry Pi (linux/arm64)

**Fixed**
- Makefile test-cycle target now uses correct gRPC method syntax for generic services

### Milestone 1: Module Foundation

**Added**
- Generic service module (`viamdemo:kettle-cycle-test:controller`) with DoCommand stub
- Unit tests for controller lifecycle (NewController, DoCommand, Close)
- Hot reload deployment workflow via `viam module reload-local`
- Makefile with build, test, and packaging targets
- Module metadata (meta.json) for Viam registry integration

**Changed**
- README updated with module structure, Milestone 1 summary, and development instructions

## [0.0.1] - 2026-01-19

### Added
- Project planning documents (product_spec.md, CLAUDE.md)
- Technical decisions for Viam components, data schema, motion constraints
- README target outline with lesson structure
- Claude Code agents for docs, changelog, test review, and retrospectives
