import logging
import struct
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcap.reader import make_reader
from mcap.writer import Writer as RawMcapWriter

from .mcap_reader import MESSAGES_TYPE, BetterOsiDecoderFactory

logger = logging.getLogger(__name__)

OSI_TRACE_METADATA_NAME: str = "net.asam.osi.trace"
OSI_CHANNEL_OSI_VERSION_KEY: str = "net.asam.osi.trace.channel.osi_version"
OSI_CHANNEL_PROTOBUF_VERSION_KEY: str = "net.asam.osi.trace.channel.protobuf_version"
OSI_CHANNEL_DESCRIPTION_KEY: str = "net.asam.osi.trace.channel.description"

OSI_TRACE_REQUIRED_METADATA_KEYS: frozenset[str] = frozenset(
    {
        "version",
        "min_osi_version",
        "max_osi_version",
        "min_protobuf_version",
        "max_protobuf_version",
    }
)

OSI_TRACE_RECOMMENDED_METADATA_KEYS: frozenset[str] = frozenset(
    {
        "zero_time",
        "creation_time",
        "description",
        "authors",
        "data_sources",
    }
)

OSI_CHANNEL_REQUIRED_METADATA_KEYS: frozenset[str] = frozenset(
    {
        OSI_CHANNEL_OSI_VERSION_KEY,
        OSI_CHANNEL_PROTOBUF_VERSION_KEY,
    }
)

OSI_CHANNEL_RECOMMENDED_METADATA_KEYS: frozenset[str] = frozenset(
    {
        OSI_CHANNEL_DESCRIPTION_KEY,
    }
)


def _get_osi_version(version: str | None = None) -> str:
    """Return the ASAM OSI version implemented by betterosi."""
    if version is not None:
        try:
            from .version_manager import module_name_to_version

            return module_name_to_version(version)
        except (ValueError, AttributeError):
            return version
    try:
        from .version_manager import DEFAULT_VERSION, load_generated_version

        gen_mod = load_generated_version(DEFAULT_VERSION)
        if hasattr(gen_mod, "osi_version_pb"):
            opts = gen_mod.osi_version_pb.desc().proto.options
            if hasattr(opts, "_unknown_fields") and 81000 in opts._unknown_fields:
                raw = opts._unknown_fields[81000][0]
                v = gen_mod.osi_version_pb.InterfaceVersion.from_binary(raw[4:])
                return f"{v.version_major}.{v.version_minor}.{v.version_patch}"
        return DEFAULT_VERSION
    except (ImportError, AttributeError, KeyError, ValueError, IndexError):
        logger.debug("Failed to determine OSI version from descriptors", exc_info=True)
    return "3.8.0"


def _get_protobuf_version() -> str:
    """Return the protobuf version (protobuf-py or google.protobuf)."""
    try:
        import google.protobuf

        return google.protobuf.__version__
    except ImportError:
        pass
    try:
        from importlib.metadata import PackageNotFoundError, version

        return version("protobuf-py")
    except (PackageNotFoundError, ImportError):
        pass
    return "proto3"


def _get_betterosi_version() -> str:
    """Return the package version of betterosi."""
    try:
        from importlib.metadata import PackageNotFoundError, version

        return version("betterosi")
    except (PackageNotFoundError, ImportError):
        return "0.8.5"


def extract_timestamp_from_filename(path: Path | str) -> str | None:
    """Extract an OSI timestamp from the trace file name if present (e.g. 20260920T220305Z)."""
    p = Path(path)
    filename = p.name
    if len(filename) >= 16:
        candidate = filename[:16]
        try:
            dt = datetime.strptime(candidate, "%Y%m%dT%H%M%SZ").replace(
                tzinfo=timezone.utc
            )
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            pass
    return None


def prepare_required_file_metadata(
    metadata: dict[str, str] | None = None,
    version: str | None = None,
) -> dict[str, str]:
    """Prepare the required 'net.asam.osi.trace' metadata with default values."""
    osi_ver = _get_osi_version(version)
    proto_ver = _get_protobuf_version()
    res = {
        "version": osi_ver,
        "min_osi_version": osi_ver,
        "max_osi_version": osi_ver,
        "min_protobuf_version": proto_ver,
        "max_protobuf_version": proto_ver,
        "creation_time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if metadata:
        res.update({k: str(v) for k, v in metadata.items()})
    return res


def prepare_channel_metadata(
    metadata: dict[str, str] | None = None,
    description: str | None = None,
    version: str | None = None,
) -> dict[str, str]:
    """Prepare channel metadata with required OSI keys and optional description."""
    res = dict(metadata) if metadata else {}
    if OSI_CHANNEL_OSI_VERSION_KEY not in res:
        res[OSI_CHANNEL_OSI_VERSION_KEY] = _get_osi_version(version)
    if OSI_CHANNEL_PROTOBUF_VERSION_KEY not in res:
        res[OSI_CHANNEL_PROTOBUF_VERSION_KEY] = _get_protobuf_version()
    if description and OSI_CHANNEL_DESCRIPTION_KEY not in res:
        res[OSI_CHANNEL_DESCRIPTION_KEY] = description
    return res


def load_descriptor_set(version: str = "3.8.0") -> bytes:
    import importlib.resources

    try:
        ref = importlib.resources.files("betterosi").joinpath(
            "generated", version, "osi3_descriptor_set.pb"
        )
        if hasattr(ref, "read_bytes"):
            return ref.read_bytes()
    except (ImportError, AttributeError, FileNotFoundError, OSError):
        pass
    p = (
        Path(__file__).resolve().parent
        / "generated"
        / version
        / "osi3_descriptor_set.pb"
    )
    return p.read_bytes()


def _load_descriptor_set(version: str = "3.8.0") -> bytes:
    return load_descriptor_set(version)


def gen2betterosi(
    schema,
    message,
    return_sensor_view=False,
    return_ground_truth=False,
    passthrough=False,
):
    if not passthrough:
        if any(schema.name == f"osi3.{k}" for k in MESSAGES_TYPE):
            return message
        else:
            return None
    if not return_sensor_view and not return_ground_truth:
        return message
    if return_sensor_view and schema.name == "osi3.SensorView":
        return message
    if return_ground_truth:
        if schema.name == "osi3.SensorView":
            return message.global_ground_truth
        if schema.name == "osi3.GroundTruth":
            return message
    return None


def iter_osi_trace_file(f, m):
    while True:
        length_bytes = f.read(4)
        if not length_bytes:
            break  # EOF
        if len(length_bytes) < 4:
            raise ValueError("Truncated length header")
        (msg_len,) = struct.unpack("<I", length_bytes)
        message = f.read(msg_len)
        if len(message) < msg_len:
            raise ValueError("Truncated message body")
        yield m.from_binary(message)


def read(
    filepath: str,
    return_sensor_view=False,
    return_ground_truth=False,
    mcap_return_betterosi: bool | None = None,
    mcap_topics: list | None = None,
    osi_message_type: str | None = None,
    version: str | None = None,
    osi_module: Any | None = None,
) -> Generator[Any]:
    if mcap_return_betterosi is not None:
        import warnings

        warnings.warn(
            "mcap_return_betterosi is deprecated and has no effect. "
            "MCAP reading always uses betterosi classes now.",
            DeprecationWarning,
            stacklevel=2,
        )

    if osi_module is None:
        from .version_manager import DEFAULT_VERSION, get_version_module

        target_version = version if version is not None else DEFAULT_VERSION
        osi_module = get_version_module(target_version)

    p = Path(filepath)
    with p.open("rb") as f:
        if p.suffix == ".mcap":
            reader = make_reader(
                f, decoder_factories=[BetterOsiDecoderFactory(osi_module=osi_module)]
            )
            views = (
                gen2betterosi(
                    schema,
                    proto_msg,
                    return_sensor_view=return_sensor_view,
                    return_ground_truth=return_ground_truth,
                    passthrough=True,
                )
                for schema, channel, message, proto_msg in reader.iter_decoded_messages(
                    topics=mcap_topics
                )
            )
            views = (v for v in views if v is not None)
        elif p.suffix == ".osi":
            if return_sensor_view or return_ground_truth:
                is_sv = False
                try:
                    with p.open("rb") as t:
                        length_bytes = t.read(4)
                        if len(length_bytes) == 4:
                            (msg_len,) = struct.unpack("<I", length_bytes)
                            first_bytes = t.read(msg_len)
                            if len(first_bytes) == msg_len:
                                try:
                                    sample_sv = osi_module.SensorView.from_binary(
                                        first_bytes
                                    )
                                    ggt = getattr(
                                        sample_sv, "global_ground_truth", None
                                    )
                                    if (
                                        ggt is not None
                                        and getattr(ggt, "timestamp", None) is not None
                                        and (
                                            ggt.timestamp.seconds is not None
                                            or ggt.timestamp.nanos is not None
                                        )
                                    ):
                                        is_sv = True
                                except (ValueError, AttributeError, KeyError) as e:
                                    logger.debug(
                                        "Failed to decode sample as SensorView: %s", e
                                    )
                except OSError as e:
                    logger.debug("Failed to read sample for type probing: %s", e)

                if return_sensor_view and not is_sv:
                    raise ValueError(
                        f"File '{filepath}' contains GroundTruth messages, not SensorView."
                    )

                if is_sv:
                    views = iter_osi_trace_file(f, osi_module.SensorView)
                    if not return_sensor_view:
                        views = (m.global_ground_truth for m in views)
                else:
                    views = iter_osi_trace_file(f, osi_module.GroundTruth)
            else:
                if osi_message_type is None:
                    raise ValueError(
                        "Specify the osi_message_type, e.g., `GroundTruth`."
                    )
                views = iter_osi_trace_file(f, getattr(osi_module, osi_message_type))
        else:
            raise NotImplementedError()
        yield from views


class Writer:
    def __init__(
        self,
        output,
        topic: str = "ground_truth",
        mode: str = "wb",
        metadata: dict[str, str] | None = None,
        channel_metadata: dict[str, dict[str, str]] | dict[str, str] | None = None,
        library: str | None = None,
        descriptor_set: bytes | None = None,
        version: str | None = None,
        **kwargs,
    ):
        p = Path(output)
        if p.suffix == ".mcap":
            self.write_mcap = True
            self.write_osi = False
            self.topic = topic
            self.file = open(p, mode)  # noqa: SIM115
            writer_kwargs = {}
            if "chunk_size" in kwargs:
                writer_kwargs["chunk_size"] = kwargs["chunk_size"]
            if "compression" in kwargs:
                writer_kwargs["compression"] = kwargs["compression"]
            self._mcap_writer = RawMcapWriter(self.file, **writer_kwargs)
            lib_str = (
                library
                if library is not None
                else f"betterosi/{_get_betterosi_version()}"
            )
            self._mcap_writer.start(library=lib_str)
            self._mcap_schemas = {}
            self._mcap_channels = {}
            self._channel_metadata = {}
            if isinstance(channel_metadata, dict):
                if any(isinstance(v, dict) for v in channel_metadata.values()):
                    self._channel_metadata.update(channel_metadata)
                else:
                    self._channel_metadata[topic] = channel_metadata

            from .version_manager import DEFAULT_VERSION, module_name_to_version

            self._version = (
                module_name_to_version(version)
                if version is not None
                else DEFAULT_VERSION
            )

            if descriptor_set is not None:
                self._descriptor_set = descriptor_set
            else:
                self._descriptor_set = load_descriptor_set(self._version)

            # Prepare and add net.asam.osi.trace file-level metadata
            file_meta = prepare_required_file_metadata(metadata, version=self._version)
            if "zero_time" not in file_meta:
                zt = extract_timestamp_from_filename(p)
                if zt:
                    file_meta["zero_time"] = zt
            self.add_metadata(OSI_TRACE_METADATA_NAME, file_meta)
        elif p.suffix == ".osi":
            self.write_mcap = False
            self.write_osi = True
            self.file = open(p, mode)  # noqa: SIM115
        else:
            raise NotImplementedError()

    def __enter__(self):
        return self

    def add_metadata(self, name: str, data: dict[str, str]):
        """Add a file-level metadata record to the MCAP file."""
        if self.write_mcap:
            self._mcap_writer.add_metadata(
                name=name, data={k: str(v) for k, v in data.items()}
            )

    def add_file_metadata(self, name: str, data: dict[str, str]):
        """Alias for add_metadata."""
        self.add_metadata(name, data)

    def register_channel(
        self,
        topic: str,
        message_or_type: Any,
        metadata: dict[str, str] | None = None,
        description: str | None = None,
    ) -> int:
        """Register a channel with its protobuf schema and OSI channel metadata."""
        if not self.write_mcap:
            raise RuntimeError("Channels can only be registered on MCAP files")
        if topic in self._mcap_channels:
            return self._mcap_channels[topic]

        if hasattr(message_or_type, "desc"):
            type_name = message_or_type.desc().type_name
        elif hasattr(type(message_or_type), "desc"):
            type_name = type(message_or_type).desc().type_name
        else:
            raise ValueError(f"Cannot determine descriptor for {message_or_type}")

        if type_name not in self._mcap_schemas:
            schema_id = self._mcap_writer.register_schema(
                name=type_name,
                encoding="protobuf",
                data=self._descriptor_set,
            )
            self._mcap_schemas[type_name] = schema_id
        else:
            schema_id = self._mcap_schemas[type_name]

        ch_meta = dict(self._channel_metadata.get(topic, {}))
        if metadata:
            ch_meta.update(metadata)
        ch_meta = prepare_channel_metadata(
            ch_meta, description=description, version=getattr(self, "_version", None)
        )

        channel_id = self._mcap_writer.register_channel(
            topic=topic,
            message_encoding="protobuf",
            schema_id=schema_id,
            metadata=ch_meta,
        )
        self._mcap_channels[topic] = channel_id
        return channel_id

    add_channel = register_channel

    def _get_mcap_channel(
        self,
        topic: str,
        message: Any,
        channel_metadata: dict[str, str] | None = None,
        description: str | None = None,
    ):
        if topic not in self._mcap_channels:
            self.register_channel(
                topic,
                message,
                metadata=channel_metadata,
                description=description,
            )
        return self._mcap_channels[topic]

    def add(
        self,
        view,
        topic: str | None = None,
        log_time=None,
        channel_metadata: dict[str, str] | None = None,
        channel_description: str | None = None,
    ):
        if self.write_mcap:
            if log_time is None:
                log_time = int(view.timestamp.nanos + view.timestamp.seconds * 1e9)
            topic = self.topic if topic is None else topic
            channel_id = self._get_mcap_channel(
                topic,
                view,
                channel_metadata=channel_metadata,
                description=channel_description,
            )
            self._mcap_writer.add_message(
                channel_id=channel_id,
                log_time=log_time,
                data=view.to_binary(),
                publish_time=log_time,
            )
        if self.write_osi:
            buffer = view.to_binary()
            self.file.write(struct.pack("<L", len(buffer)))
            self.file.write(buffer)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ):
        if self.write_mcap:
            self._mcap_writer.finish()
        self.file.close()


def make_version_writer(version: str, descriptor_set: bytes | None = None):
    class VersionWriter(Writer):
        def __init__(
            self,
            output,
            topic="ground_truth",
            mode="wb",
            metadata: dict[str, str] | None = None,
            channel_metadata: dict[str, dict[str, str]] | dict[str, str] | None = None,
            library: str | None = None,
            **kwargs,
        ):
            super().__init__(
                output,
                topic=topic,
                mode=mode,
                metadata=metadata,
                channel_metadata=channel_metadata,
                library=library,
                descriptor_set=descriptor_set,
                version=version,
                **kwargs,
            )

    VersionWriter.__name__ = "Writer"
    VersionWriter.__qualname__ = f"v{version.replace('.', '_')}.Writer"
    return VersionWriter


def make_version_read(version: str, osi_module: Any):
    def bound_read(
        filepath: str,
        return_sensor_view=False,
        return_ground_truth=False,
        mcap_return_betterosi: bool | None = None,
        mcap_topics: list | None = None,
        osi_message_type: str | None = None,
    ) -> Generator[Any]:
        return read(
            filepath,
            return_sensor_view=return_sensor_view,
            return_ground_truth=return_ground_truth,
            mcap_return_betterosi=mcap_return_betterosi,
            mcap_topics=mcap_topics,
            osi_message_type=osi_message_type,
            version=version,
            osi_module=osi_module,
        )

    bound_read.__name__ = "read"
    bound_read.__qualname__ = f"v{version.replace('.', '_')}.read"
    return bound_read


def make_version_decoder_factory(version: str, osi_module: Any):
    class VersionDecoderFactory(BetterOsiDecoderFactory):
        def __init__(self):
            super().__init__(osi_module=osi_module, version=version)

    VersionDecoderFactory.__name__ = "BetterOsiDecoderFactory"
    VersionDecoderFactory.__qualname__ = (
        f"v{version.replace('.', '_')}.BetterOsiDecoderFactory"
    )
    return VersionDecoderFactory


def read_file_metadata(filepath: str | Path) -> list[dict[str, Any]]:
    """Read all file-level metadata records from an MCAP file."""
    p = Path(filepath)
    with p.open("rb") as f:
        reader = make_reader(f)
        return [
            {"name": m.name, "data": dict(m.metadata)} for m in reader.iter_metadata()
        ]


def read_channel_metadata(filepath: str | Path) -> dict[str, dict[str, str]]:
    """Read channel metadata from an MCAP file, returned as topic -> metadata mapping."""
    p = Path(filepath)
    with p.open("rb") as f:
        reader = make_reader(f)
        summary = reader.get_summary()
        if summary is None:
            return {}
        return {ch.topic: dict(ch.metadata) for ch in summary.channels.values()}
