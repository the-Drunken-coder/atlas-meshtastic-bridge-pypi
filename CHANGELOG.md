# Changelog

## [0.1.24] - 2026-03-05

- Added path traversal protection to gateway operation loading by validating module names against an allow-list and strict regex pattern before dynamic import
- Restricted operation imports to only modules explicitly defined in the command map
- Hardened mode profile loading to prevent directory traversal when resolving JSON file paths
- Migrated mode file I/O from `importlib.resources` to `pathlib` for explicit path validation and control
- Removed stale setuptools egg-info metadata files from source distribution

## [0.1.23] - 2026-03-03

- Marked package as deprecated in README with prominent warning that this is the legacy Meshtastic bridge
- Updated PyPI package description to `[LEGACY]` status and directed users to `next_gen_atlas_meshtastic_link` replacement
- Documented maintenance-mode status: existing deployments remain supported but new projects should migrate

## [0.1.22] - 2026-03-02

- Synchronized source from ATLAS monorepo commit 8c4f4ba
- Refactored test_config.py and test_gateway.py to use centralized MOCK_API_TOKEN constant in place of hardcoded strings
- Updated PKG-INFO metadata to align version tracking with current release

## [0.1.21] - 2026-03-01

- Relaxed `create_entity` type constraints to accept raw dictionaries for the `components` parameter, allowing plain dict inputs without requiring `EntityComponents` or `TaskComponents` instances.
- Removed `TypeError` enforcement that previously rejected non-typed component inputs in the typed client API.
- Updated `test_client_typed_api.py` to verify acceptance of raw dictionary components and adjusted test formatting.
- Synchronized package source with ATLAS monorepo at commit 471e309.

## [0.1.20] - 2026-02-21

- Renamed `operations.tasks.start_task` to `operations.tasks.acknowledge_task` to reflect updated task lifecycle semantics.
- Improved connection handling and error recovery in the Meshtastic client.
- Enhanced message deduplication logic for gateway operations.
- Updated gateway task listing and hardware harness command presets.
- Synchronized all changes from upstream ATLAS monorepo (commit 348d027).

## [0.1.19] - 2026-02-20

- Synchronized source from upstream ATLAS monorepo (commit 4486a6a).
- Updated package metadata to version 0.1.19.
- Refreshed test suite for operations list tasks.
- Internal maintenance and dependency alignment.

## [0.1.18] - 2026-02-20

- Synchronized source from upstream ATLAS monorepo (commit a1830f6).
- Updated client implementation with latest improvements.
- Refined task listing operations.
- Added dedicated test suite for list tasks functionality.

## [0.1.17] - 2026-02-20
- Synced changes from the ATLAS monorepo.
- Version bump to 0.1.17.
- Internal updates and maintenance.

## [0.1.16] - 2026-02-20

- Synchronized package metadata with upstream ATLAS monorepo (commit 1a0db81)
- Updated `pyproject.toml` version and dependency specifications
- Maintenance release with no user-facing API changes

## [0.1.15] - 2026-02-19
- Synced changes from the ATLAS monorepo.
- Version bump to 0.1.15.
- Internal updates and maintenance.

## [0.1.14] - 2026-02-19

- Routine synchronization from upstream ATLAS monorepo (9a23649)
- Internal updates to client implementation and operations components
- Internal updates to hardware harness tooling and command presets
- Documentation refinements

## [0.1.13] - 2026-02-18

- Synchronized package with latest upstream monorepo changes
- Updated internal module structure to match source repository layout
- Refactored internal utilities for consistency
- No functional changes or new features in this release

All notable changes to this package will be documented in this file.

The source code is mirrored from the ATLAS monorepo into `package/`.
