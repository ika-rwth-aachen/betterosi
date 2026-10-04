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
