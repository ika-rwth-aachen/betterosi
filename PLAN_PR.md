# Plan: fix blocking review findings for `protobuf-py` → `main`

Review at `ceabfa4` found four blocking issues. This plan fixes all four, adds a regression test for each,
and uses `make_proof_files.py` as the acceptance check.

## 0. Prerequisites

- `make_proof_files.py` has been saved to the repo root (untracked). The baseline on `ceabfa4` is
  confirmed: all 4 findings print `REPRODUCED` and the script exits with status 1.
  ```bash
  PYTHONPATH=. uv run python make_proof_files.py
  ```
  The script writes `gt_with_traffic_light.osi`, `bare_schema_name.mcap` and
  `sv_without_ground_truth.osi` to the repo root. Add these three files to `.gitignore`, or delete them,
  so they are not committed by accident.
- The script depends on the private `Writer` attributes `_mcap_writer` and `_descriptor_set`.
  Do **not** rename them during the fix.
- Facts about the protobuf-py API (checked against the installed version):
  - Unset scalars return `0`/`""`. Unset message fields return `None`. To check whether a field is
    present, use `msg.has_field("name")`. Never use `x is not None` on scalars.
  - `protobuf.merge_from_binary(message, data, *, ignore_unknown_fields=False)` fills an existing
    message in place.
  - `Message.desc().fields` and `msg.clear_field(name)` exist, so a message can be cleared.
  - Unknown fields are stored on `msg._unknown_fields` (`dict[int, list[bytes]] | None`).

---

## 1. Finding 1 + 4: decide the `.osi` message type without guessing first

**Files:** `betterosi/io.py` (`read()`, the `.osi` branch at lines ~290–338), `betterosi/osi2mcap.py`

### 1.1 New helper `_resolve_osi_message_type(path, osi_message_type, osi_module) -> str`

Resolve the type in this order and stop at the first step that gives an answer:

1. **Explicit `osi_message_type`.** Use it even when `return_ground_truth` or `return_sensor_view` is
   set. Today it is ignored in that case.
2. **OSI trace file naming convention.** Split `Path(path).stem` on `_`. If one of the tokens is a known
   type abbreviation, use that type:
   `gt→GroundTruth`, `sv→SensorView`, `sd→SensorData`, `svc→SensorViewConfiguration`,
   `hvd→HostVehicleData`, `tc→TrafficCommand`, `tcu→TrafficCommandUpdate`, `tu→TrafficUpdate`,
   `mr→MotionRequest`, `su→StreamingUpdate`.
   Prefer the token right after a leading `YYYYMMDDTHHMMSSZ` timestamp. If no timestamp is present,
   accept the type token only when exactly one token matches, so names like `my_sv_gt_test.osi` are
   not misread.
3. **Wire probe, as a last resort** (`_probe_osi_message_type`, see 1.2). If the probe cannot decide,
   raise
   `ValueError("Could not determine the OSI message type of '<file>'. Pass osi_message_type=... or name the file following the OSI trace naming convention (e.g. *_gt_*.osi / *_sv_*.osi).")`

### 1.2 Rewrite the probe (`_probe_osi_message_type(first_bytes, osi_module) -> str | None`)

- Decode the first frame as **both** `SensorView` and `GroundTruth`. If decoding fails with a
  wire-type mismatch or `ValueError`, that interpretation is rejected.
- Walk each decoded message recursively and reject the interpretation if it has any unknown fields
  (`_unknown_fields`). A real GroundTruth decoded as SensorView usually produces unknown or mismatched
  nested fields, for example `MovingObject` read as `MountingPosition`. The reverse is also true.
- SensorView is accepted only if it decodes cleanly **and** `sv.has_field("global_ground_truth")`.
  The old `timestamp.seconds is not None` checks are removed.
- Exactly one interpretation is clean → return it. Both clean or neither clean → return `None`, which
  makes the caller raise. The probe never falls back to GroundTruth silently.
- Catch only the specific decode exceptions and log them at debug level, as today.
- **Verified on the reviewer's files:** protobuf-py `from_binary` does **not** raise on a wire-type
  mismatch. It stores the field in `_unknown_fields`, so the rejection logic only needs to walk the
  decoded message recursively and collect unknown fields:

  | First frame of | as SensorView | as GroundTruth | Probe result |
  |---|---|---|---|
  | `gt_with_traffic_light.osi` | unknowns at `.mounting_position_rmse.position`, `.global_ground_truth.timestamp` | clean | **GroundTruth** ✔ |
  | `sv_without_ground_truth.osi` | clean, but no `global_ground_truth` | clean | **ambiguous → `None`** |

  The SensorView in finding 4 (`version`, `timestamp`, `sensor_id`) is byte-for-byte a valid
  GroundTruth (`version`, `timestamp`, `host_vehicle_id`). No probe can tell them apart, so for
  this case only `osi_message_type` or the file name can give the right answer. That is why the
  resolution order in 1.1 matters, and why the probe must raise instead of guessing.

### 1.3 Apply the resolved type in `read()`

- `return_sensor_view=True`:
  - resolved type `SensorView` → yield the SensorView messages.
  - otherwise → `ValueError(f"File '{filepath}' contains {resolved} messages, not SensorView.")`.
    This message is only used when the type was actually determined. The undetermined case uses the
    message from 1.1.3.
- `return_ground_truth=True`:
  - `GroundTruth` → yield as is.
  - `SensorView` → yield `m.global_ground_truth` **only for frames where `m.has_field("global_ground_truth")`**.
    Skip frames without it and log one warning per file. This matches the MCAP path, where
    `None` results are already filtered out.
  - any other type → `ValueError` (the file cannot provide GroundTruth).
- Conflicting arguments, for example `osi_message_type="GroundTruth"` together with
  `return_sensor_view=True`, or both `return_*` flags set → `ValueError` up front.
- With no `return_*` flag, behaviour stays the same, but `osi_message_type` may now also be taken from
  the file name (step 1.1.2) before the existing "Specify the osi_message_type" error is raised.

### 1.4 `osi2mcap`

- Always pass `osi_message_type` to `read()` together with `return_ground_truth` /
  `return_sensor_view`. The CLI's explicit choice then wins and no probing happens.

---

## 2. Finding 2: `msg.ParseFromString(data)` must fill `msg` in place

**File:** `betterosi/deprecation.py` (`_patch_parse_methods`, lines ~271–292)

- Replace the `classmethod` with a small descriptor (or a function that checks `isinstance(cls_or_self, type)`)
  so both kinds of call work:
  - **Instance call** `msg.ParseFromString(data)` / `msg.parse(data)`:
    1. Clear all fields of `msg`: `for f in msg.desc().fields: msg.clear_field(f.name)`, and also reset
       unknown fields. This matches the semantics of Google protobuf's `ParseFromString`.
    2. `protobuf.merge_from_binary(msg, data)`.
    3. Return `msg`. betterproto2's `parse` returned `self`, so chained use keeps working. Note that
       Google's `ParseFromString` returns the number of bytes read. We keep returning the message,
       for compatibility with code written against betterproto2 on `main`.
  - **Class call** `GroundTruth.ParseFromString(data)` → `cls.from_binary(data)`, as today.
- Keep the `DeprecationWarning` text and `stacklevel=2`. Factor the shared body of `ParseFromString` /
  `parse` into one helper so the two methods cannot diverge.
- **Tests** (`tests/test_deprecation.py`, around lines 155–185): in `test_parse_from_string_warning` and
  `test_parse_warning`:
  - start from an **empty** `betterosi.GroundTruth()`, call `gt.ParseFromString(data)` without
    using the return value, and assert on `gt` itself (`gt.version.version_major == 3`, etc.);
  - assert that previously set fields that are not in `data` are cleared;
  - assert that the return value `is gt`;
  - keep the class-level assertions.

---

## 3. Finding 3: bare schema names (`GroundTruth` instead of `osi3.GroundTruth`) in MCAP

**Files:** `betterosi/io.py` (`gen2betterosi`, topic selection in `read()`), `betterosi/mcap_reader.py`

- Add one helper, e.g. `osi_type_name(schema) -> str | None` in `mcap_reader.py`. It returns
  `schema.name.split(".")[-1]` if that is in `MESSAGES_TYPE` and the prefix is empty or `osi3`,
  otherwise `None`. Use it in **all three** places:
  - `BetterOsiDecoderFactory.decoder_for` (replaces the inline `split(".")`),
  - topic auto-selection in `read()` (replaces `startswith("osi3.") or name in MESSAGES_TYPE`),
  - `gen2betterosi`: compare `type_name == "SensorView"` / `"GroundTruth"` instead of the full
    `osi3.*` string.
- Also fix the `passthrough=False` branch of `gen2betterosi`. It currently returns early and ignores
  `return_sensor_view` / `return_ground_truth` (listed as non-blocking finding). Change it to: reject
  unknown schemas, then apply the same filter logic as the passthrough branch.
- **Test:** write an MCAP with schema name `GroundTruth` (and one with bare `SensorView`) and assert that
  `read()` and `read(return_ground_truth=True)` both return all messages. For SensorView, also check
  `return_sensor_view=True`.

---

## 4. Regression tests (`tests/test_osi_reader.py`)

Each of these must fail on `ceabfa4` and pass after the fix:

| Test | Covers |
|---|---|
| GT `.osi` (name without convention) whose first frame has a `TrafficLight` with `id` **and `base`** (position/dimension set), plus moving objects → `read(return_ground_truth=True)` returns the full GT. `read(return_sensor_view=True)` raises "not SensorView" | F1 |
| Same file named `20260101T000000Z_gt_380_700_1_x.osi` → resolved from the file name. The probe is not called (monkeypatch `_probe_osi_message_type` to raise) | F1 |
| `osi_message_type="GroundTruth"` together with `return_ground_truth=True` is honoured. A conflicting combination raises | F1 |
| SV `.osi` without `global_ground_truth`, named `*_sv_*.osi` → `return_sensor_view=True` yields a SensorView. `return_ground_truth=True` yields nothing (frame skipped) and warns, and does **not** return a GT built from SV bytes | F4 |
| Same SV file with a name that does not follow the convention → `ValueError` saying "Could not determine", not "contains GroundTruth" | F4 |
| Empty / truncated `.osi` with `return_*` → "Could not determine" (or truncation) error, not silently GT | F4 |
| `osi2mcap --osi-message-type SensorView` on an SV file without the naming convention works | F1/F4 |
| Existing `test_read_ground_truth_with_traffic_lights` / `test_read_sensor_view_file` keep passing. Update the asserted error text if needed | — |

Plus the deprecation tests (§2) and the MCAP bare-schema tests (§3).

---

## 4a. How `make_proof_files.py` will pass

| Finding | Script check | Mechanism after the fix |
|---|---|---|
| 1 | `read(gt_with_traffic_light.osi, return_ground_truth=True) == read(..., osi_message_type="GroundTruth")` | The name has exactly one type token (`gt`) → GroundTruth (§1.1.2). The probe would also choose GroundTruth (§1.2), and a test with a non-convention name covers that path |
| 2 | `msg.ParseFromString(data)`; `msg == returned` | In-place merge, returns `msg` itself (§2) |
| 3 | `len(read(bare))  == len(read(bare, return_ground_truth=True))` | Shared `osi_type_name()` in `gen2betterosi` (§3) |
| 4 | `type(next(read(sv_without_ground_truth.osi, return_sensor_view=True))) is SensorView` | The name has exactly one type token (`sv`) → SensorView (§1.1.2). `return_ground_truth=True` then yields nothing instead of a fake GT (§1.3) |

> [!IMPORTANT]
> Findings 1 and 4 in the script pass because of the loose file-name rule ("exactly one known type
> token in the stem"), not because of the probe. The probe alone can only fix finding 1. Finding 4
> cannot be decided from the bytes (see the table in §1.2). If the name rule were limited to strict
> convention names (`<timestamp>_<type>_…`), finding 4 would raise "Could not determine…", which is
> correct behaviour, but the script would still print `REPRODUCED`. Mention this in the reply to the
> reviewer.

---

## 5. Order of work

1. ~~Add `make_proof_files.py` locally and confirm the 4× `REPRODUCED` baseline.~~ Done (exit 1).
2. Write the failing regression tests from §2, §3 and §4 first.
3. Fix F2 (`deprecation.py`). It is small and independent.
4. Fix F3 (shared schema-name helper, `gen2betterosi`).
5. Fix F1 + F4 (`_resolve_osi_message_type`, new probe, `read()` changes, `osi2mcap`).
6. Run `uv run pytest` (baseline: 41 passed, 4 skipped, plus the new tests) and `uv run ruff check . && uv run ruff format --check .`.
7. `PYTHONPATH=. uv run python make_proof_files.py` must print `not reproduced` for all 4 and exit 0.
8. Reply to the review with one line per finding linking to the fix commit and the test that covers it.

## 6. Non-blocking findings (optional, separate commits)

Not required for merge. Do them in this PR only if they stay small:

- `gen2betterosi` ignoring filters when `passthrough=False`, fixed as part of §3.
- Deprecated-alias lookup implemented three times → merge into one function in `deprecation.py`.
- `__version__` still `0.8.5` → bump to match `pyproject.toml`.
- `Writer` silently dropping most `**kwargs` → warn or raise on unknown kwargs.
- `Writer` not checking the OSI version of written messages → warn when `msg.version` does not match
  the writer's version.
- `CLAUDE.md` / `README.md` contradicting the repository layout → update the docs.

---

## 7. Implementation status (2026-10-19)

All four blocking findings are fixed. They are not committed yet.

- `make_proof_files.py`: all 4 `not reproduced`, exit 0.
- `pytest`: 65 passed, 4 skipped (baseline 41 passed / 4 skipped). Every new regression test was
  checked to **fail on `ceabfa4`**. `ruff check` and `ruff format --check` are clean.

Where the implementation differs from the plan:

- **SensorView without `global_ground_truth`, `return_ground_truth=True`:** frames without it are
  skipped, and one `UserWarning` reports the count. If **no** frame in the file has it, a
  `ValueError` is raised instead of silently yielding nothing. This is what the script's finding 4
  now prints.
- **`tests/test_versions.py::test_write_and_read_osi_v3_7_0`** now passes
  `osi_message_type="GroundTruth"`. Its file `trace_37.osi` contains only `version` + `timestamp`,
  which is byte-identical as SensorView and GroundTruth. Before, it passed only because of the old
  silent fall-back to GroundTruth.
- **Parse shim:** protobuf-py's `_unknown_fields` attribute cannot be reassigned, so it is cleared in
  place. The descriptor binds with `types.MethodType`, so the `DeprecationWarning` still points at
  the caller (covered by a test).
- **New public helpers:** `betterosi.io.osi_message_type_from_filename`,
  `betterosi.io.OSI_TRACE_TYPE_ABBREVIATIONS`, `betterosi.mcap_reader.osi_type_name`.

Non-blocking findings (all 6 implemented and tested):
- `gen2betterosi` ignores filters when `passthrough=False`: fixed to apply filters.
- `Writer` silently dropping most kwargs: all MCAP options forwarded; unknown kwargs raise `TypeError`; MCAP options on `.osi` writer emit `UserWarning`.
- `Writer` not checking OSI version of written message: cross-version message class raises `ValueError`; mismatched `InterfaceVersion` emits `UserWarning`.
- `__version__` still at 0.8.5: dynamically resolves from package metadata (`0.9.0`).
- Deprecated-alias lookup implemented 3 times: unified in `resolve_deprecated_name` in `deprecation.py`.
- `CLAUDE.md` / `README.md` contradicting repository layout: updated references (removed `osi3trace.py`, removed `buf.yaml`, updated `tests/` directory description, corrected `mcap_topics`).
