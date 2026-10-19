"""Reproduce review findings 1-4 for the protobuf-py branch.

1. GroundTruth .osi whose traffic lights have a `base` is misdetected as SensorView
2. `msg.ParseFromString(data)` no longer fills `msg` in place
3. MCAP with a bare schema name (`GroundTruth`) loses messages when a filter is set
4. SensorView .osi without `global_ground_truth` in the first message is
   classified as GroundTruth

Writes three trace files next to this script:
  gt_with_traffic_light.osi, bare_schema_name.mcap, sv_without_ground_truth.osi

Run from the repo root:  PYTHONPATH=. python make_proof_files.py
Exits with status 1 if any finding reproduces.
"""

import sys
import warnings
from pathlib import Path

import betterosi

warnings.simplefilter("ignore", DeprecationWarning)

OUT = Path(__file__).parent
GT_OSI_FILE = OUT / "gt_with_traffic_light.osi"
BARE_MCAP_FILE = OUT / "bare_schema_name.mcap"
SV_OSI_FILE = OUT / "sv_without_ground_truth.osi"
N_FRAMES = 3

reproduced: dict[int, bool] = {}


def version() -> betterosi.InterfaceVersion:
    return betterosi.InterfaceVersion(version_major=3, version_minor=8, version_patch=0)


def ground_truth(i: int, with_traffic_light: bool = False) -> betterosi.GroundTruth:
    return betterosi.GroundTruth(
        version=version(),
        timestamp=betterosi.Timestamp(seconds=i, nanos=0),
        host_vehicle_id=betterosi.Identifier(value=1),
        moving_object=[
            betterosi.MovingObject(id=betterosi.Identifier(value=1)),
            betterosi.MovingObject(id=betterosi.Identifier(value=2)),
        ],
        traffic_light=(
            [
                betterosi.TrafficLight(
                    id=betterosi.Identifier(value=42),
                    # `base` is what triggers the misdetection: it is field 2,
                    # which the SensorView probe decodes as GroundTruth.timestamp.
                    base=betterosi.BaseStationary(
                        position=betterosi.Vector3d(x=1.0, y=2.0, z=3.0)
                    ),
                )
            ]
            if with_traffic_light
            else []
        ),
    )


def describe(gt) -> str:
    return (
        f"timestamp={gt.timestamp}, version={gt.version}, "
        f"moving_objects={len(gt.moving_object)}, traffic_lights={len(gt.traffic_light)}"
    )


def attempt(fn) -> str:
    try:
        return str(fn())
    except ValueError as e:
        return f"raised {type(e).__name__}: {e}"


def verdict(number: int, is_reproduced: bool):
    reproduced[number] = is_reproduced
    print("=> REPRODUCED" if is_reproduced else "=> not reproduced")
    print()


# --- Finding 1 -------------------------------------------------------------
print("=== Finding 1: GroundTruth .osi with traffic lights read as SensorView ===")
with betterosi.Writer(GT_OSI_FILE) as w:
    for i in range(N_FRAMES):
        w.add(ground_truth(i, with_traffic_light=True))
print(f"wrote {GT_OSI_FILE.name}")

print("written          :", describe(ground_truth(0, True)))
explicit = next(betterosi.read(GT_OSI_FILE, osi_message_type="GroundTruth"))
print("read, explicit   :", describe(explicit))
auto = next(betterosi.read(GT_OSI_FILE, return_ground_truth=True))
print("read, autodetect :", describe(auto))
verdict(1, auto != explicit)

# --- Finding 2 -------------------------------------------------------------
print("=== Finding 2: msg.ParseFromString(data) does not fill msg ===")
data = ground_truth(5).to_binary()
msg = betterosi.GroundTruth()
returned = msg.ParseFromString(data)
print("msg after call   :", describe(msg))
print("returned value   :", describe(returned))
verdict(2, msg != returned)

# --- Finding 3 -------------------------------------------------------------
print("=== Finding 3: MCAP with bare schema name `GroundTruth` ===")
with betterosi.Writer(BARE_MCAP_FILE) as w:
    raw = w._mcap_writer
    schema_id = raw.register_schema(
        name="GroundTruth",  # no `osi3.` prefix
        encoding="protobuf",
        data=w._descriptor_set,
    )
    channel_id = raw.register_channel(
        topic="ground_truth", message_encoding="protobuf", schema_id=schema_id
    )
    for i in range(N_FRAMES):
        raw.add_message(
            channel_id=channel_id,
            log_time=i * 10**9,
            publish_time=i * 10**9,
            data=ground_truth(i).to_binary(),
        )
print(f"wrote {BARE_MCAP_FILE.name}")

n_all = len(list(betterosi.read(BARE_MCAP_FILE)))
n_gt = len(list(betterosi.read(BARE_MCAP_FILE, return_ground_truth=True)))
print(f"read()                         : {n_all} messages")
print(f"read(return_ground_truth=True) : {n_gt} messages")
verdict(3, n_all != n_gt)

# --- Finding 4 -------------------------------------------------------------
print("=== Finding 4: SensorView .osi without global_ground_truth ===")
with betterosi.Writer(SV_OSI_FILE) as w:
    for i in range(N_FRAMES):
        w.add(
            betterosi.SensorView(
                version=version(),
                timestamp=betterosi.Timestamp(seconds=i, nanos=0),
                sensor_id=betterosi.Identifier(value=7),
            )
        )
print(f"wrote {SV_OSI_FILE.name}")

explicit_sv = next(betterosi.read(SV_OSI_FILE, osi_message_type="SensorView"))
print("read, explicit SensorView      :", type(explicit_sv).__name__)
as_sv = attempt(
    lambda: type(next(betterosi.read(SV_OSI_FILE, return_sensor_view=True))).__name__
)
print("read(return_sensor_view=True)  :", as_sv)
as_gt = attempt(
    lambda: repr(next(betterosi.read(SV_OSI_FILE, return_ground_truth=True)))
)
print("read(return_ground_truth=True) :", as_gt)
verdict(4, as_sv != "SensorView")

# --- Summary ---------------------------------------------------------------
print("=== Summary ===")
for number, is_reproduced in reproduced.items():
    print(f"finding {number}: {'REPRODUCED' if is_reproduced else 'not reproduced'}")
sys.exit(1 if any(reproduced.values()) else 0)
