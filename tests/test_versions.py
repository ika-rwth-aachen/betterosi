import pytest

import betterosi
from betterosi import v3_7_0, v3_8_0


def test_available_versions():
    versions = betterosi.get_available_versions()
    assert "3.7.0" in versions
    assert "3.8.0" in versions


def test_default_version_is_3_8_0():
    assert betterosi.DEFAULT_VERSION == "3.8.0"
    assert betterosi.__version_osi__ == "3.8.0"

    gt_default = betterosi.GroundTruth()
    gt_38 = v3_8_0.GroundTruth()
    gt_37 = v3_7_0.GroundTruth()

    assert type(gt_default) is type(gt_38)
    assert type(gt_default) is not type(gt_37)


def test_version_import_as():
    from betterosi import v3_7_0 as b_37
    from betterosi import v3_8_0 as b_38

    assert b_37.__version_osi__ == "3.7.0"
    assert b_38.__version_osi__ == "3.8.0"

    assert hasattr(b_37, "GroundTruth")
    assert hasattr(b_38, "GroundTruth")
    assert hasattr(b_37, "Writer")
    assert hasattr(b_38, "Writer")
    assert hasattr(b_37, "read")
    assert hasattr(b_38, "read")


def test_submodule_import():
    import betterosi.v3_7_0 as sub_37
    import betterosi.v3_8_0 as sub_38
    from betterosi.v3_7_0 import GroundTruth as GT37
    from betterosi.v3_8_0 import GroundTruth as GT38

    assert sub_37 is v3_7_0
    assert sub_38 is v3_8_0
    assert GT37 is v3_7_0.GroundTruth
    assert GT38 is v3_8_0.GroundTruth


def test_deprecation_on_versions():
    # Capitalization alias
    with pytest.deprecated_call(match=r"'Vector3D' is deprecated"):
        vec37 = v3_7_0.Vector3D(x=1.0, y=2.0, z=3.0)
    assert isinstance(vec37, v3_7_0.Vector3d)

    with pytest.deprecated_call(match=r"'Vector3D' is deprecated"):
        vec38 = v3_8_0.Vector3D(x=1.0, y=2.0, z=3.0)
    assert isinstance(vec38, v3_8_0.Vector3d)

    # ParseFromString method patch
    raw = vec37.to_binary()
    with pytest.deprecated_call(match=r"Vector3d\.ParseFromString is deprecated"):
        parsed = v3_7_0.Vector3d.ParseFromString(raw)
    assert parsed.x == 1.0

    # EnumWrapper
    assert hasattr(v3_7_0, "MovingObjectType")
    assert hasattr(v3_8_0, "MovingObjectType")
    assert v3_7_0.MovingObjectType.UNKNOWN == v3_7_0.MovingObject.Type.UNKNOWN
    assert v3_8_0.MovingObjectType.UNKNOWN == v3_8_0.MovingObject.Type.UNKNOWN


def test_write_and_read_osi_v3_7_0(tmp_path):
    trace_file = str(tmp_path / "trace_37.osi")

    gt = v3_7_0.GroundTruth(
        version=v3_7_0.InterfaceVersion(
            version_major=3, version_minor=7, version_patch=0
        ),
        timestamp=v3_7_0.Timestamp(seconds=1, nanos=0),
    )

    with v3_7_0.Writer(trace_file) as writer:
        writer.add(gt)

    messages = list(v3_7_0.read(trace_file, return_ground_truth=True))
    assert len(messages) == 1
    assert isinstance(messages[0], v3_7_0.GroundTruth)
    assert messages[0].version.version_minor == 7


def test_write_and_read_mcap_v3_7_0(tmp_path):
    mcap_file = str(tmp_path / "trace_37.mcap")

    gt = v3_7_0.GroundTruth(
        version=v3_7_0.InterfaceVersion(
            version_major=3, version_minor=7, version_patch=0
        ),
        timestamp=v3_7_0.Timestamp(seconds=1, nanos=0),
    )

    with v3_7_0.Writer(mcap_file) as writer:
        writer.add(gt)

    messages = list(v3_7_0.read(mcap_file, return_ground_truth=True))
    assert len(messages) == 1
    assert isinstance(messages[0], v3_7_0.GroundTruth)
    assert messages[0].version.version_minor == 7


def test_write_and_read_mcap_v3_8_0(tmp_path):
    mcap_file = str(tmp_path / "trace_38.mcap")

    gt = v3_8_0.GroundTruth(
        version=v3_8_0.InterfaceVersion(
            version_major=3, version_minor=8, version_patch=0
        ),
        timestamp=v3_8_0.Timestamp(seconds=1, nanos=0),
    )

    with v3_8_0.Writer(mcap_file) as writer:
        writer.add(gt)

    messages = list(v3_8_0.read(mcap_file, return_ground_truth=True))
    assert len(messages) == 1
    assert isinstance(messages[0], v3_8_0.GroundTruth)
    assert messages[0].version.version_minor == 8


def test_dir_contains_version_symbols():
    d = dir(betterosi)
    assert "v3_7_0" in d
    assert "v3_8_0" in d
    assert "GroundTruth" in d
    assert "Writer" in d
    assert "read" in d
