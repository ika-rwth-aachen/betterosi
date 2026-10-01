from collections.abc import Callable
from typing import Any

from mcap.decoder import DecoderFactory
from mcap.records import Schema

MESSAGES_TYPE = [
    "SensorView",
    "SensorViewConfiguration",
    "GroundTruth",
    "HostVehicleData",
    "SensorData",
    "TrafficCommand",
    "TrafficCommandUpdate",
    "TrafficUpdate",
    "MotionRequest",
    "StreamingUpdate",
    "MapAsamOpenDrive",
]


class BetterOsiDecoderFactory(DecoderFactory):
    """MCAP DecoderFactory that decodes directly into betterosi (protobuf-py) classes."""

    def __init__(self, osi_module: Any | None = None, version: str | None = None):
        self._osi = osi_module
        self._version = version

    def _get_osi_module(self):
        if self._osi is None:
            from .version_manager import DEFAULT_VERSION, get_version_module

            target_version = (
                self._version if self._version is not None else DEFAULT_VERSION
            )
            self._osi = get_version_module(target_version)
        return self._osi

    def decoder_for(
        self, message_encoding: str, schema: Schema | None
    ) -> Callable[[bytes], Any] | None:
        if message_encoding != "protobuf":
            return None
        if schema is None or schema.encoding != "protobuf":
            return None

        type_name = schema.name.split(".")[-1]
        if type_name not in MESSAGES_TYPE:
            return None

        osi_mod = self._get_osi_module()
        message_cls = getattr(osi_mod, type_name, None)
        if message_cls is None:
            return None

        return message_cls.from_binary
