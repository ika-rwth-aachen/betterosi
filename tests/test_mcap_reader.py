from pathlib import Path

from mcap.writer import Writer

import betterosi


def test_read_mcap_with_non_osi_channel(tmp_path: Path):
    path = tmp_path / "mixed.mcap"
    with path.open("wb") as f:
        w = Writer(f)
        w.start()

        # OSI GroundTruth channel
        gt = betterosi.GroundTruth(
            timestamp=betterosi.Timestamp(seconds=5, nanos=100),
            moving_object=[betterosi.MovingObject(id=betterosi.Identifier(value=10))],
        )
        sid_gt = w.register_schema(
            name="osi3.GroundTruth", encoding="protobuf", data=b""
        )
        cid_gt = w.register_channel(
            topic="ground_truth", message_encoding="protobuf", schema_id=sid_gt
        )
        w.add_message(
            channel_id=cid_gt, log_time=1000, data=gt.to_binary(), publish_time=1000
        )

        # Non-OSI channel (e.g. demo.Note or foxglove.SceneUpdate)
        sid_note = w.register_schema(name="demo.Note", encoding="protobuf", data=b"")
        cid_note = w.register_channel(
            topic="notes", message_encoding="protobuf", schema_id=sid_note
        )
        w.add_message(
            channel_id=cid_note,
            log_time=2000,
            data=b"some binary payload",
            publish_time=2000,
        )

        w.finish()

    # 1. Read without mcap_topics: should gracefully skip non-OSI channel without DecoderNotFoundError
    msgs = list(betterosi.read(str(path)))
    assert len(msgs) == 1
    assert isinstance(msgs[0], betterosi.GroundTruth)
    assert msgs[0].timestamp.seconds == 5
    assert msgs[0].moving_object[0].id.value == 10

    # 2. Read with return_ground_truth=True
    msgs_gt = list(betterosi.read(str(path), return_ground_truth=True))
    assert len(msgs_gt) == 1
    assert msgs_gt[0].moving_object[0].id.value == 10

    # 3. Read with explicit topic
    msgs_topic = list(betterosi.read(str(path), mcap_topics=["ground_truth"]))
    assert len(msgs_topic) == 1
    assert msgs_topic[0].timestamp.seconds == 5
