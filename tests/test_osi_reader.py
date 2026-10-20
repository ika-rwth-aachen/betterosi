from pathlib import Path

import pytest

import betterosi


def test_read_ground_truth_with_traffic_lights(tmp_path: Path):
    gt = betterosi.GroundTruth(
        timestamp=betterosi.Timestamp(seconds=1, nanos=0),
        moving_object=[betterosi.MovingObject(id=betterosi.Identifier(value=1))],
        traffic_light=[betterosi.TrafficLight(id=betterosi.Identifier(value=42))],
    )
    osi_path = tmp_path / "gt_with_tl.osi"
    with betterosi.Writer(str(osi_path)) as w:
        w.add(gt)

    # 1. Read with explicit osi_message_type
    msg_explicit = next(betterosi.read(str(osi_path), osi_message_type="GroundTruth"))
    assert msg_explicit.timestamp.seconds == 1
    assert len(msg_explicit.moving_object) == 1
    assert msg_explicit.moving_object[0].id.value == 1
    assert len(msg_explicit.traffic_light) == 1
    assert msg_explicit.traffic_light[0].id.value == 42

    # 2. Read with return_ground_truth=True
    msg_gt = next(betterosi.read(str(osi_path), return_ground_truth=True))
    assert msg_gt.timestamp.seconds == 1
    assert len(msg_gt.moving_object) == 1
    assert msg_gt.moving_object[0].id.value == 1
    assert len(msg_gt.traffic_light) == 1
    assert msg_gt.traffic_light[0].id.value == 42

    # 3. Read with return_sensor_view=True must raise ValueError instead of returning garbage
    with pytest.raises(ValueError, match="not SensorView"):
        next(betterosi.read(str(osi_path), return_sensor_view=True))


def test_read_sensor_view_file(tmp_path: Path):
    sv = betterosi.SensorView(
        timestamp=betterosi.Timestamp(seconds=2, nanos=0),
        global_ground_truth=betterosi.GroundTruth(
            timestamp=betterosi.Timestamp(seconds=2, nanos=0),
            moving_object=[betterosi.MovingObject(id=betterosi.Identifier(value=99))],
        ),
    )
    osi_path = tmp_path / "sv.osi"
    with betterosi.Writer(str(osi_path)) as w:
        w.add(sv)

    # Read with return_sensor_view=True
    msg_sv = next(betterosi.read(str(osi_path), return_sensor_view=True))
    assert isinstance(msg_sv, betterosi.SensorView)
    assert msg_sv.timestamp.seconds == 2
    assert msg_sv.global_ground_truth.timestamp.seconds == 2

    # Read with return_ground_truth=True
    msg_gt = next(betterosi.read(str(osi_path), return_ground_truth=True))
    assert isinstance(msg_gt, betterosi.GroundTruth)
    assert msg_gt.timestamp.seconds == 2
    assert msg_gt.moving_object[0].id.value == 99


# --- Regression tests for review findings 1, 3 and 4 -----------------------


def _version():
    return betterosi.InterfaceVersion(version_major=3, version_minor=8, version_patch=0)


def _gt_with_positioned_traffic_light(i: int = 0) -> betterosi.GroundTruth:
    return betterosi.GroundTruth(
        version=_version(),
        timestamp=betterosi.Timestamp(seconds=i, nanos=0),
        host_vehicle_id=betterosi.Identifier(value=1),
        moving_object=[
            betterosi.MovingObject(id=betterosi.Identifier(value=1)),
            betterosi.MovingObject(id=betterosi.Identifier(value=2)),
        ],
        traffic_light=[
            betterosi.TrafficLight(
                id=betterosi.Identifier(value=42),
                # Field 2 of TrafficLight; lands on GroundTruth.timestamp when the
                # frame is misread as SensorView.global_ground_truth.
                base=betterosi.BaseStationary(
                    position=betterosi.Vector3d(x=1.0, y=2.0, z=3.0)
                ),
            )
        ],
    )


def _sv_without_ground_truth(i: int = 0) -> betterosi.SensorView:
    return betterosi.SensorView(
        version=_version(),
        timestamp=betterosi.Timestamp(seconds=i, nanos=0),
        sensor_id=betterosi.Identifier(value=7),
    )


def _write_osi(path: Path, messages) -> Path:
    with betterosi.Writer(path) as w:
        for m in messages:
            w.add(m)
    return path


def test_gt_with_traffic_light_base_is_probed_as_ground_truth(tmp_path: Path):
    """Finding 1, probe path: file name gives no type."""
    expected = [_gt_with_positioned_traffic_light(i) for i in range(3)]
    osi_path = _write_osi(tmp_path / "trace.osi", expected)

    got = list(betterosi.read(osi_path, return_ground_truth=True))
    assert got == expected
    assert got[0].traffic_light[0].base.position.z == 3.0

    with pytest.raises(
        ValueError, match="contains GroundTruth messages, not SensorView"
    ):
        next(betterosi.read(osi_path, return_sensor_view=True))


def test_type_from_file_name_skips_probe(tmp_path: Path, monkeypatch):
    """Finding 1, naming-convention path: the probe must not be consulted."""
    from betterosi import io

    def _fail(*args, **kwargs):
        raise AssertionError("probe must not run when the file name gives the type")

    monkeypatch.setattr(io, "_probe_osi_message_type", _fail)
    expected = [_gt_with_positioned_traffic_light()]
    osi_path = _write_osi(tmp_path / "20260101T000000Z_gt_380_700_1_x.osi", expected)
    assert list(betterosi.read(osi_path, return_ground_truth=True)) == expected


def test_explicit_message_type_is_honoured_with_return_flags(
    tmp_path: Path, monkeypatch
):
    from betterosi import io

    monkeypatch.setattr(
        io, "_probe_osi_message_type", lambda *a, **k: pytest.fail("probe called")
    )
    expected = [_gt_with_positioned_traffic_light()]
    osi_path = _write_osi(tmp_path / "trace.osi", expected)
    got = list(
        betterosi.read(
            osi_path, return_ground_truth=True, osi_message_type="GroundTruth"
        )
    )
    assert got == expected

    with pytest.raises(
        ValueError, match="contains GroundTruth messages, not SensorView"
    ):
        next(
            betterosi.read(
                osi_path, return_sensor_view=True, osi_message_type="GroundTruth"
            )
        )


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("20260920T220305Z_gt_380_700_10_x.osi", "GroundTruth"),
        ("20260920T220305Z_sv_380_700_10_x.osi", "SensorView"),
        ("20260920T220305Z_xx_380_700_10_sv.osi", None),
        ("gt_with_traffic_light.osi", "GroundTruth"),
        ("sv_without_ground_truth.osi", "SensorView"),
        ("my_sv_vs_gt.osi", None),
        ("trace.osi", None),
        ("svc_config.osi", "SensorViewConfiguration"),
    ],
)
def test_osi_message_type_from_filename(name, expected):
    from betterosi.io import osi_message_type_from_filename

    assert osi_message_type_from_filename(name) == expected


def test_sv_without_ground_truth_by_file_name(tmp_path: Path):
    """Finding 4: SensorView without global_ground_truth, named by convention."""
    expected = [_sv_without_ground_truth(i) for i in range(3)]
    osi_path = _write_osi(tmp_path / "20260101T000000Z_sv_380_700_3_x.osi", expected)

    got = list(betterosi.read(osi_path, return_sensor_view=True))
    assert got == expected
    assert all(isinstance(m, betterosi.SensorView) for m in got)

    # Must not fabricate a GroundTruth from SensorView bytes.
    with pytest.raises(ValueError, match="without global_ground_truth"):
        list(betterosi.read(osi_path, return_ground_truth=True))


def test_sv_partially_without_ground_truth_skips_and_warns(tmp_path: Path):
    with_gt = betterosi.SensorView(
        version=_version(),
        timestamp=betterosi.Timestamp(seconds=1, nanos=0),
        global_ground_truth=betterosi.GroundTruth(
            timestamp=betterosi.Timestamp(seconds=1, nanos=0)
        ),
    )
    osi_path = _write_osi(tmp_path / "x_sv.osi", [_sv_without_ground_truth(0), with_gt])
    with pytest.warns(UserWarning, match="Skipped 1 SensorView frame"):
        got = list(betterosi.read(osi_path, return_ground_truth=True))
    assert got == [with_gt.global_ground_truth]


def test_sv_without_ground_truth_unknown_name_cannot_be_determined(tmp_path: Path):
    """Finding 4: the bytes are ambiguous, so the reader must not guess."""
    osi_path = _write_osi(tmp_path / "trace.osi", [_sv_without_ground_truth()])
    for kwargs in ({"return_sensor_view": True}, {"return_ground_truth": True}):
        with pytest.raises(ValueError, match="Could not determine"):
            next(betterosi.read(osi_path, **kwargs))
    # The explicit type still works.
    msg = next(
        betterosi.read(osi_path, return_sensor_view=True, osi_message_type="SensorView")
    )
    assert isinstance(msg, betterosi.SensorView)
    assert msg.sensor_id.value == 7


@pytest.mark.parametrize("content", [b"", b"\x10\x00\x00\x00\x01\x02"])
def test_empty_or_truncated_osi_is_not_treated_as_ground_truth(tmp_path: Path, content):
    osi_path = tmp_path / "trace.osi"
    osi_path.write_bytes(content)
    with pytest.raises(ValueError, match="Could not determine"):
        next(betterosi.read(osi_path, return_ground_truth=True))


def test_osi2mcap_sensor_view_without_naming_convention(tmp_path: Path):
    from typer.testing import CliRunner

    from betterosi.osi2mcap import app

    expected = [_sv_without_ground_truth(i) for i in range(2)]
    osi_path = _write_osi(tmp_path / "trace.osi", expected)
    mcap_path = tmp_path / "out.mcap"
    result = CliRunner().invoke(
        app,
        [str(osi_path), "--output", str(mcap_path), "--osi-message-type", "SensorView"],
    )
    assert result.exit_code == 0, result.output
    assert list(betterosi.read(mcap_path, return_sensor_view=True)) == expected


def _write_bare_schema_mcap(path: Path, type_name: str, messages) -> Path:
    with betterosi.Writer(path) as w:
        raw = w._mcap_writer
        schema_id = raw.register_schema(
            name=type_name, encoding="protobuf", data=w._descriptor_set
        )
        channel_id = raw.register_channel(
            topic="bare", message_encoding="protobuf", schema_id=schema_id
        )
        for i, m in enumerate(messages):
            raw.add_message(
                channel_id=channel_id,
                log_time=i * 10**9,
                publish_time=i * 10**9,
                data=m.to_binary(),
            )
    return path


def test_mcap_bare_ground_truth_schema_name(tmp_path: Path):
    """Finding 3: bare `GroundTruth` schema name must survive the GT filter."""
    expected = [_gt_with_positioned_traffic_light(i) for i in range(3)]
    path = _write_bare_schema_mcap(tmp_path / "bare.mcap", "GroundTruth", expected)
    assert list(betterosi.read(path)) == expected
    assert list(betterosi.read(path, return_ground_truth=True)) == expected
    assert list(betterosi.read(path, return_sensor_view=True)) == []


def test_mcap_bare_sensor_view_schema_name(tmp_path: Path):
    gt = betterosi.GroundTruth(timestamp=betterosi.Timestamp(seconds=1, nanos=0))
    sv = betterosi.SensorView(version=_version(), global_ground_truth=gt)
    path = _write_bare_schema_mcap(tmp_path / "bare_sv.mcap", "SensorView", [sv])
    assert list(betterosi.read(path)) == [sv]
    assert list(betterosi.read(path, return_sensor_view=True)) == [sv]
    assert list(betterosi.read(path, return_ground_truth=True)) == [gt]


def test_gen2betterosi_filters_without_passthrough():
    from types import SimpleNamespace

    gt = betterosi.GroundTruth(timestamp=betterosi.Timestamp(seconds=1, nanos=0))
    sv = betterosi.SensorView(global_ground_truth=gt)
    gt_schema = SimpleNamespace(name="osi3.GroundTruth")
    sv_schema = SimpleNamespace(name="SensorView")
    other = SimpleNamespace(name="foo.Bar")

    assert betterosi.gen2betterosi(gt_schema, gt) is gt
    assert betterosi.gen2betterosi(other, gt) is None
    assert betterosi.gen2betterosi(gt_schema, gt, return_sensor_view=True) is None
    assert betterosi.gen2betterosi(sv_schema, sv, return_ground_truth=True) == gt
    assert (
        betterosi.gen2betterosi(
            sv_schema, betterosi.SensorView(), return_ground_truth=True
        )
        is None
    )
