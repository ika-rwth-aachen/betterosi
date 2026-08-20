# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

betterosi is a Python library for reading and writing ASAM Open-Simulation-Interface (OSI) trace files using bufbuild's protobuf-py for typed Python protobuf classes. It supports both `.osi` (binary length-prefixed protobuf) and `.mcap` (Foxglove MCAP container) formats.

## Commands

### Install dependencies
```bash
uv sync --all-extras --dev
```

### Run tests
```bash
uv run pytest
```
Tests are code blocks embedded in `README.md`, executed via `pytest-codeblocks`. There is no separate test directory.

### Lint and format
```bash
uv run ruff check --fix .
uv run ruff format .
```

### Run pre-commit hooks
```bash
uv run pre-commit run --all-files
```

### Regenerate protobuf code
```bash
uv run python gen_protos.py
```
This runs `buf generate` and `buf build` for each version directory in `osi-proto/<version>/` (e.g. `3.7.0`, `3.8.0`) to produce typed Python code into `betterosi/generated/<version>/` (gitignored), and builds `osi3_descriptor_set.pb` for MCAP schema registration.

### CLI tools
```bash
uv run betterosi-viewer <file>        # Visualize OSI GroundTruth files
uv run betterosi-to-mcap <file>       # Convert .osi to .mcap
```

## Architecture

### Multi-Version Support
- Proto definitions reside in `osi-proto/<version>/` (e.g. `osi-proto/3.7.0/`, `osi-proto/3.8.0/`)
- `gen_protos.py` automatically discovers all version directories and compiles them to `betterosi/generated/<version>/`
- `betterosi.version_manager` provides dynamic version discovery, module creation, and descriptor set loading
- By default, `betterosi` uses OSI 3.8.0 identically to the previous single-version behavior
- Specific versions can be imported via `from betterosi import v3_7_0 as betterosi` or `from betterosi import v3_8_0 as betterosi`
- To add a new version in the future, simply add `osi-proto/<version>/` and run `python gen_protos.py`; the version will be automatically discovered and accessible as `v<major>_<minor>_<patch>`

### Code Generation Pipeline
1. `osi-proto/<version>/` contains versioned ASAM OSI protobuf definitions (plus custom `MapAsamOpenDrive`)
2. `gen_protos.py` runs `buf generate` using the `protoc-gen-py` plugin and builds descriptor sets
3. Output lands in `betterosi/generated/<version>/` (created at build time via hatch build hook)

### Package Structure
- `betterosi/__init__.py` — Re-exports default version (3.8.0) generated classes for a flat API (`betterosi.GroundTruth`, `betterosi.SensorView`, etc.), exports version modules (`v3_7_0`, `v3_8_0`), wraps enums in `EnumWrapper`, and provides dynamic `__getattr__` resolution
- `betterosi/version_manager.py` — Version discovery, dynamic loading of generated modules, and `VersionModule` lifecycle management
- `betterosi/io.py` — Core read/write API: `read()` generator and `Writer` context manager supporting versioning for both `.osi` and `.mcap` formats
- `betterosi/mcap_reader.py` — Version-aware `BetterOsiDecoderFactory`
- `betterosi/deprecation.py` — Handles enum wrapping, method monkey-patching (`ParseFromString`), capitalization aliases (`Vector3D` -> `Vector3d`), and nested message aliases
- `betterosi/osi2mcap.py` — Typer CLI for `.osi` → `.mcap` conversion
- `betterosi/viewer.py` — matplotlib-based OSI GroundTruth visualization CLI

### Key Design Decisions
- The `EnumWrapper` class exists because protobuf-py nests enums inside their parent message class (e.g., `MovingObject.Type`); the wrapper flattens them to top-level names (e.g., `MovingObjectType`) and allows access by both stripped and original proto names
- Backward-compat aliases exist for names that differ from betterproto2's capitalization (`Vector3D` → `Vector3d`, etc.)
- `.osi` files use little-endian 4-byte length-prefixed messages (no container metadata)
- MCAP writing uses the raw `mcap.writer.Writer` with a pre-built `FileDescriptorSet` for schema registration
- The build system (hatchling + hatch-build-scripts) runs code generation automatically during `uv sync` / `uv build`

## Linting
- Ruff is the sole linter/formatter
- `E741` (ambiguous variable names) and `E701` (multiple statements on one line) are suppressed
- Python 3.10+ is the minimum supported version
