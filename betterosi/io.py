import inspect
import logging
import re
import struct
import warnings
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcap.reader import make_reader
from mcap.writer import Writer as RawMcapWriter
from protobuf import Message as _ProtobufMessage

from .mcap_reader import BetterOsiDecoderFactory, osi_type_name

logger = logging.getLogger(__name__)

# Keyword arguments accepted by mcap.writer.Writer (everything except `output`).
_MCAP_WRITER_OPTIONS: frozenset[str] = frozenset(
    name
    for name in inspect.signature(RawMcapWriter.__init__).parameters
    if name not in ("self", "output")
)

# Generated message classes live in e.g. `betterosi.generated._v3_7_0.osi_groundtruth_pb`.
_GENERATED_MODULE_VERSION_RE = re.compile(r"\._v(\d+)_(\d+)_(\d+)\.")

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
    """Return the ASAM OSI protobuf version (7.0.0)."""  # pretending to be the latest version of python protobuf for compatibilitys
    return "7.0.0"


def _get_betterosi_version() -> str:
    """Return the package version of betterosi (from pyproject.toml via the installed metadata)."""
    try:
        from importlib.metadata import PackageNotFoundError, version

        return version("betterosi")
    except (PackageNotFoundError, ImportError):
        return "0+unknown"


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
    """Filter or convert one decoded MCAP message.

    ``passthrough=False`` drops messages whose schema is not an OSI top-level
    message. ``passthrough=True`` lets them through as long as no filter is set.
    Both ``osi3.<Type>`` and bare ``<Type>`` schema names are accepted.
    """
    type_name = osi_type_name(schema)
    if not passthrough and type_name is None:
        return None
    if not return_sensor_view and not return_ground_truth:
        return message
    if return_sensor_view and type_name == "SensorView":
        return message
    if return_ground_truth:
        if type_name == "SensorView":
            if not message.has_field("global_ground_truth"):
                return None
            return message.global_ground_truth
        if type_name == "GroundTruth":
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


# Message type abbreviations of the ASAM OSI trace file naming convention
# (<timestamp>_<type>_<osi version>_<protobuf version>_<frames>_<custom>.osi).
OSI_TRACE_TYPE_ABBREVIATIONS: dict[str, str] = {
    "gt": "GroundTruth",
    "sv": "SensorView",
    "sd": "SensorData",
    "svc": "SensorViewConfiguration",
    "hvd": "HostVehicleData",
    "tc": "TrafficCommand",
    "tcu": "TrafficCommandUpdate",
    "tu": "TrafficUpdate",
    "mr": "MotionRequest",
    "su": "StreamingUpdate",
}

_OSI_TRACE_TIMESTAMP_RE = re.compile(r"^\d{8}T\d{6}Z$")


def osi_message_type_from_filename(path: Path | str) -> str | None:
    """Return the OSI message type encoded in a trace file name, or ``None``.

    If the name starts with an OSI timestamp (``20260920T220305Z_gt_...``), the
    token after it is used. Otherwise the type is accepted only when exactly one
    distinct type abbreviation appears among the ``_``-separated parts of the
    name, so ambiguous names such as ``sv_vs_gt.osi`` give ``None``.
    """
    tokens = Path(path).stem.lower().split("_")
    if len(tokens) > 1 and _OSI_TRACE_TIMESTAMP_RE.match(tokens[0].upper()):
        return OSI_TRACE_TYPE_ABBREVIATIONS.get(tokens[1])
    found = {
        OSI_TRACE_TYPE_ABBREVIATIONS[t]
        for t in tokens
        if t in OSI_TRACE_TYPE_ABBREVIATIONS
    }
    if len(found) == 1:
        return found.pop()
    return None


def _has_unknown_fields(msg) -> bool:
    """Return True if ``msg`` or any nested message holds unknown fields."""
    if getattr(msg, "_unknown_fields", None):
        return True
    for field in msg.desc().fields:
        value = getattr(msg, field.name, None)
        if isinstance(value, dict):
            values = value.values()
        elif isinstance(value, (list, tuple)):
            values = value
        else:
            values = (value,)
        for v in values:
            if isinstance(v, _ProtobufMessage) and _has_unknown_fields(v):
                return True
    return False


def _probe_osi_message_type(first_bytes: bytes, osi_module: Any) -> str | None:
    """Guess whether a frame is a SensorView or a GroundTruth.

    The frame is decoded as both types. In protobuf-py a wire-type mismatch is
    stored as an unknown field, so the wrong interpretation usually shows up
    as unknown fields somewhere in the decoded tree. Exactly one clean
    interpretation gives the answer. If both are clean, the bytes really are
    ambiguous (e.g. a SensorView with only version/timestamp/sensor_id is a
    valid GroundTruth with version/timestamp/host_vehicle_id) and ``None`` is
    returned.
    """
    clean = []
    for type_name in ("SensorView", "GroundTruth"):
        try:
            msg = getattr(osi_module, type_name).from_binary(first_bytes)
        except ValueError as e:
            logger.debug("First frame does not decode as %s: %s", type_name, e)
            continue
        if _has_unknown_fields(msg):
            logger.debug("First frame decoded as %s has unknown fields", type_name)
            continue
        clean.append(type_name)
    if len(clean) == 1:
        return clean[0]
    return None


def _read_first_frame(f) -> bytes | None:
    """Read the first length-prefixed frame of an open .osi file and rewind it."""
    try:
        length_bytes = f.read(4)
        if len(length_bytes) < 4:
            return None
        (msg_len,) = struct.unpack("<I", length_bytes)
        data = f.read(msg_len)
        return data if len(data) == msg_len else None
    finally:
        f.seek(0)


def _resolve_osi_message_type(
    f, path: Path, osi_message_type: str | None, osi_module: Any, probe: bool
) -> str | None:
    """Work out the message type of an .osi file.

    Order: explicit ``osi_message_type``, then the trace file naming convention,
    then (only if ``probe``) decoding the first frame.
    """
    if osi_message_type is not None:
        return osi_message_type
    from_name = osi_message_type_from_filename(path)
    if from_name is not None:
        return from_name
    if not probe:
        return None
    first = _read_first_frame(f)
    if first is None:
        return None
    return _probe_osi_message_type(first, osi_module)


def _ground_truth_from_sensor_views(views, filepath):
    """Yield ``global_ground_truth`` of each SensorView.

    Frames without ``global_ground_truth`` are skipped and reported in one
    warning. If no frame has one, a ``ValueError`` is raised instead of
    silently returning nothing.
    """
    yielded = skipped = 0
    for sv in views:
        if sv.has_field("global_ground_truth"):
            yielded += 1
            yield sv.global_ground_truth
        else:
            skipped += 1
    if skipped and not yielded:
        raise ValueError(
            f"File '{filepath}' contains SensorView messages without "
            "global_ground_truth, so no GroundTruth can be returned."
        )
    if skipped:
        warnings.warn(
            f"Skipped {skipped} SensorView frame(s) in '{filepath}' without "
            "global_ground_truth.",
            UserWarning,
            stacklevel=2,
        )


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
            decoder_factory = BetterOsiDecoderFactory(osi_module=osi_module)
            reader = make_reader(f)
            topics = mcap_topics
            if topics is None:
                summary = reader.get_summary()
                if summary is not None:
                    osi_topics = [
                        channel.topic
                        for channel in summary.channels.values()
                        if osi_type_name(summary.schemas.get(channel.schema_id))
                        is not None
                    ]
                    if osi_topics:
                        topics = osi_topics

            decoders: dict[int, Any] = {}

            def _decode(schema, channel, message):
                chid = channel.id
                if chid not in decoders:
                    decoders[chid] = decoder_factory.decoder_for(
                        channel.message_encoding, schema
                    )
                dec = decoders[chid]
                if dec is None:
                    return None
                return dec(message.data)

            decoded_messages = (
                (schema, _decode(schema, channel, message))
                for schema, channel, message in reader.iter_messages(topics=topics)
            )
            views = (
                gen2betterosi(
                    schema,
                    proto_msg,
                    return_sensor_view=return_sensor_view,
                    return_ground_truth=return_ground_truth,
                    passthrough=True,
                )
                for schema, proto_msg in decoded_messages
                if proto_msg is not None
            )
            views = (v for v in views if v is not None)
        elif p.suffix == ".osi":
            want_filter = bool(return_sensor_view or return_ground_truth)
            msg_type = _resolve_osi_message_type(
                f, p, osi_message_type, osi_module, probe=want_filter
            )
            if msg_type is None:
                if want_filter:
                    raise ValueError(
                        f"Could not determine the OSI message type of '{filepath}'. "
                        "Pass osi_message_type=... or name the file following the "
                        "OSI trace file naming convention "
                        "(e.g. *_gt_*.osi / *_sv_*.osi)."
                    )
                raise ValueError("Specify the osi_message_type, e.g., `GroundTruth`.")
            message_cls = getattr(osi_module, msg_type, None)
            if message_cls is None:
                raise ValueError(f"Unknown OSI message type '{msg_type}'.")
            views = iter_osi_trace_file(f, message_cls)
            if want_filter:
                if return_ground_truth and msg_type == "SensorView":
                    if not return_sensor_view:
                        views = _ground_truth_from_sensor_views(views, filepath)
                elif not (
                    (return_sensor_view and msg_type == "SensorView")
                    or (return_ground_truth and msg_type == "GroundTruth")
                ):
                    wanted = "SensorView" if return_sensor_view else "GroundTruth"
                    if return_sensor_view and return_ground_truth:
                        wanted = "SensorView or GroundTruth"
                    raise ValueError(
                        f"File '{filepath}' contains {msg_type} messages, not {wanted}."
                    )
        else:
            raise NotImplementedError()
        yield from views


class Writer:
    """Write OSI messages to an ``.osi`` trace or an ``.mcap`` file.

    Extra keyword arguments are passed on to :class:`mcap.writer.Writer`
    (e.g. ``chunk_size``, ``compression``, ``use_chunking``). Unknown names
    raise ``TypeError``. For ``.osi`` output, MCAP-only options are ignored with
    a warning.

    ``add()`` checks that each message belongs to the writer's OSI version: a
    message class from another ``betterosi.v<x>_<y>_<z>`` module raises
    ``ValueError``, and an ``InterfaceVersion`` field that differs from the
    writer's version gives a one-time ``UserWarning``.
    """

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
        unknown = sorted(set(kwargs) - _MCAP_WRITER_OPTIONS)
        if unknown:
            raise TypeError(
                f"Writer() got unexpected keyword argument(s): {', '.join(unknown)}. "
                f"Supported MCAP options: {', '.join(sorted(_MCAP_WRITER_OPTIONS))}."
            )

        from .version_manager import DEFAULT_VERSION, module_name_to_version

        self._version = (
            module_name_to_version(version) if version is not None else DEFAULT_VERSION
        )
        self._warned_interface_version = False

        if p.suffix == ".mcap":
            self.write_mcap = True
            self.write_osi = False
            self.topic = topic
            self.file = open(p, mode)  # noqa: SIM115
            self._mcap_writer = RawMcapWriter(self.file, **kwargs)
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
            mcap_only = {
                "metadata": metadata,
                "channel_metadata": channel_metadata,
                "library": library,
                "descriptor_set": descriptor_set,
                **kwargs,
            }
            ignored = sorted(k for k, v in mcap_only.items() if v is not None)
            if ignored:
                warnings.warn(
                    f"Writer options {', '.join(ignored)} only apply to MCAP output "
                    f"and are ignored for '{p.name}'.",
                    UserWarning,
                    stacklevel=2,
                )
            self.write_mcap = False
            self.write_osi = True
            self.file = open(p, mode)  # noqa: SIM115
        else:
            raise NotImplementedError()

    def _check_message_version(self, view) -> None:
        """Make sure ``view`` belongs to the OSI version this writer declares."""
        m = _GENERATED_MODULE_VERSION_RE.search(type(view).__module__)
        if m is not None:
            msg_version = ".".join(m.groups())
            if msg_version != self._version:
                raise ValueError(
                    f"Cannot write a {type(view).__name__} from OSI {msg_version} "
                    f"with a Writer for OSI {self._version}. Use "
                    f"betterosi.v{msg_version.replace('.', '_')}.Writer or "
                    f"Writer(..., version='{msg_version}')."
                )
        if self._warned_interface_version:
            return
        try:
            if not view.has_field("version"):
                return
        except (AttributeError, KeyError, ValueError):
            return
        v = view.version
        field_version = f"{v.version_major}.{v.version_minor}.{v.version_patch}"
        if field_version != self._version:
            warnings.warn(
                f"{type(view).__name__}.version is {field_version}, but the Writer "
                f"declares OSI {self._version}.",
                UserWarning,
                stacklevel=3,
            )
            self._warned_interface_version = True

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
        self._check_message_version(view)
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
                descriptor_set=(
                    descriptor_set if Path(output).suffix == ".mcap" else None
                ),
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
