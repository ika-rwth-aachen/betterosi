from pathlib import Path

from mcap.reader import make_reader

import betterosi


def test_default_file_metadata(tmp_path: Path):
    out_file = tmp_path / "default_metadata.mcap"
    gt = betterosi.GroundTruth(
        version=betterosi.InterfaceVersion(
            version_major=3, version_minor=8, version_patch=0
        ),
        timestamp=betterosi.Timestamp(seconds=1, nanos=0),
    )
    with betterosi.Writer(out_file) as w:
        w.add(gt)

    with open(out_file, "rb") as f:
        reader = make_reader(f)
        header = reader.get_header()
        assert header is not None
        assert header.library.startswith("betterosi")

        metadata_records = {m.name: dict(m.metadata) for m in reader.iter_metadata()}
        assert "net.asam.osi.trace" in metadata_records
        osi_meta = metadata_records["net.asam.osi.trace"]

        assert osi_meta["version"] == betterosi.__version_osi__
        assert osi_meta["min_osi_version"] == betterosi.__version_osi__
        assert osi_meta["max_osi_version"] == betterosi.__version_osi__
        assert "min_protobuf_version" in osi_meta
        assert "max_protobuf_version" in osi_meta
        assert osi_meta["min_protobuf_version"] == osi_meta["max_protobuf_version"]
        assert "creation_time" in osi_meta

        # Check channel metadata
        summary = reader.get_summary()
        assert summary is not None
        channels = list(summary.channels.values())
        assert len(channels) == 1
        ch = channels[0]
        assert ch.topic == "ground_truth"
        assert (
            ch.metadata["net.asam.osi.trace.channel.osi_version"]
            == betterosi.__version_osi__
        )
        assert (
            ch.metadata["net.asam.osi.trace.channel.protobuf_version"]
            == osi_meta["min_protobuf_version"]
        )


def test_custom_file_metadata_and_extra_records(tmp_path: Path):
    out_file = tmp_path / "custom_metadata.mcap"
    gt = betterosi.GroundTruth(
        version=betterosi.InterfaceVersion(
            version_major=3, version_minor=8, version_patch=0
        ),
        timestamp=betterosi.Timestamp(seconds=1, nanos=0),
    )
    custom_trace_meta = {
        "description": "Simulation run #42",
        "authors": "Test Suite",
        "data_sources": "Synthetic generator",
    }
    with betterosi.Writer(out_file, metadata=custom_trace_meta) as w:
        w.add_metadata("custom.experiment", {"run_id": "42", "weather": "rain"})
        w.add(gt)

    meta_records = {
        m["name"]: m["data"] for m in betterosi.read_file_metadata(out_file)
    }
    assert "net.asam.osi.trace" in meta_records
    osi_meta = meta_records["net.asam.osi.trace"]
    assert osi_meta["description"] == "Simulation run #42"
    assert osi_meta["authors"] == "Test Suite"
    assert osi_meta["data_sources"] == "Synthetic generator"
    # Required keys still present
    assert osi_meta["version"] == betterosi.__version_osi__
    assert osi_meta["min_osi_version"] == betterosi.__version_osi__
    assert "creation_time" in osi_meta

    assert "custom.experiment" in meta_records
    assert meta_records["custom.experiment"] == {"run_id": "42", "weather": "rain"}


def test_channel_metadata_customization(tmp_path: Path):
    out_file = tmp_path / "channel_metadata.mcap"
    gt = betterosi.GroundTruth(
        version=betterosi.InterfaceVersion(
            version_major=3, version_minor=8, version_patch=0
        ),
        timestamp=betterosi.Timestamp(seconds=1, nanos=0),
    )
    sv = betterosi.SensorView(
        version=betterosi.InterfaceVersion(
            version_major=3, version_minor=8, version_patch=0
        ),
        timestamp=betterosi.Timestamp(seconds=1, nanos=0),
    )

    with betterosi.Writer(out_file) as w:
        w.register_channel(
            "gt_channel",
            betterosi.GroundTruth,
            description="Environment ground truth",
            metadata={"custom_channel_key": "custom_val"},
        )
        w.add(gt, topic="gt_channel")
        w.add(
            sv,
            topic="sv_channel",
            channel_description="Front radar sensor view",
        )

    ch_meta = betterosi.read_channel_metadata(out_file)
    assert "gt_channel" in ch_meta
    assert "sv_channel" in ch_meta

    gt_m = ch_meta["gt_channel"]
    assert gt_m["net.asam.osi.trace.channel.osi_version"] == betterosi.__version_osi__
    assert "net.asam.osi.trace.channel.protobuf_version" in gt_m
    assert gt_m["net.asam.osi.trace.channel.description"] == "Environment ground truth"
    assert gt_m["custom_channel_key"] == "custom_val"

    sv_m = ch_meta["sv_channel"]
    assert sv_m["net.asam.osi.trace.channel.osi_version"] == betterosi.__version_osi__
    assert sv_m["net.asam.osi.trace.channel.description"] == "Front radar sensor view"


def test_zero_time_extraction_from_filename(tmp_path: Path):
    filename = "20260920T220305Z_sv_3.7.0_10_42_example.mcap"
    out_file = tmp_path / filename
    gt = betterosi.GroundTruth(
        version=betterosi.InterfaceVersion(
            version_major=3, version_minor=7, version_patch=0
        ),
        timestamp=betterosi.Timestamp(seconds=1, nanos=0),
    )
    with betterosi.Writer(out_file) as w:
        w.add(gt)

    meta_records = {
        m["name"]: m["data"] for m in betterosi.read_file_metadata(out_file)
    }
    osi_meta = meta_records["net.asam.osi.trace"]
    assert osi_meta["zero_time"] == "2026-09-20T22:03:05Z"


def test_osi2mcap_metadata(tmp_path: Path):
    from typer.testing import CliRunner

    from betterosi.osi2mcap import app

    osi_file = tmp_path / "20260920T220305Z_gt.osi"
    gt = betterosi.GroundTruth(
        version=betterosi.InterfaceVersion(
            version_major=3, version_minor=7, version_patch=0
        ),
        timestamp=betterosi.Timestamp(seconds=1, nanos=0),
    )
    with betterosi.Writer(osi_file) as w:
        w.add(gt)

    mcap_file = tmp_path / "converted.mcap"
    runner = CliRunner()
    result = runner.invoke(app, [str(osi_file), "--output", str(mcap_file)])
    assert result.exit_code == 0

    meta_records = {
        m["name"]: m["data"] for m in betterosi.read_file_metadata(mcap_file)
    }
    osi_meta = meta_records["net.asam.osi.trace"]
    assert osi_meta["zero_time"] == "2026-09-20T22:03:05Z"
    assert osi_meta["description"] == f"Converted from {osi_file.name}"


def test_version_specific_writer_metadata(tmp_path: Path):
    out_file = tmp_path / "v370_metadata.mcap"
    gt = betterosi.v3_7_0.GroundTruth(
        version=betterosi.v3_7_0.InterfaceVersion(
            version_major=3, version_minor=7, version_patch=0
        ),
        timestamp=betterosi.v3_7_0.Timestamp(seconds=1, nanos=0),
    )
    with betterosi.v3_7_0.Writer(out_file) as w:
        w.add(gt)

    meta_records = {
        m["name"]: m["data"] for m in betterosi.read_file_metadata(out_file)
    }
    assert "net.asam.osi.trace" in meta_records
    osi_meta = meta_records["net.asam.osi.trace"]
    assert osi_meta["version"] == "3.7.0"
    assert osi_meta["min_osi_version"] == "3.7.0"
    assert osi_meta["max_osi_version"] == "3.7.0"

    ch_meta = betterosi.read_channel_metadata(out_file)
    assert ch_meta["ground_truth"]["net.asam.osi.trace.channel.osi_version"] == "3.7.0"


def test_protobuf_version_is_proto3():
    from betterosi.io import _get_protobuf_version

    assert _get_protobuf_version() == "3.0.0"
