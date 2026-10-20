from importlib.metadata import PackageNotFoundError, version

from hatchling.metadata.plugin.interface import MetadataHookInterface


class CustomMetadataHook(MetadataHookInterface):
    def update(self, metadata: dict) -> None:
        try:
            gen_ver = version("protoc-gen-py")
            parts = gen_ver.split(".")
            major, minor = parts[0], parts[1]
            protobuf_dep = f"protobuf-py>={major}.{minor}.0,<{major}.{int(minor) + 1}.0"
        except (PackageNotFoundError, IndexError, ValueError):
            protobuf_dep = "protobuf-py"

        metadata["dependencies"] = [
            protobuf_dep,
            "mcap",
            "typer",
        ]
