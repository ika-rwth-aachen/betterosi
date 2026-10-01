{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  packages = [
    pkgs.uv

    # C compiler and pkg-config for building wheels from source
    pkgs.gcc
    pkgs.pkg-config
    pkgs.gnumake

    # Native C libraries commonly required by Python extensions
    pkgs.libffi
    pkgs.zlib
    pkgs.libjpeg
  ];

  shellHook = ''
    # Prevent uv from trying to download standalone python interpreters that bypass nix
    # (Forces uv to use the Python installed/managed in your shell or virtualenv)
    export UV_PYTHON_PREFERENCE="system"

    # Export paths for compiler/pkg-config when uv compiles wheels from sdist
    export CPATH="${pkgs.libffi.dev}/include:${pkgs.zlib.dev}/include:${pkgs.libjpeg.dev}/include:$CPATH"
    export LIBRARY_PATH="${pkgs.libffi}/lib:${pkgs.zlib}/lib:${pkgs.libjpeg}/lib:$LIBRARY_PATH"
    export PKG_CONFIG_PATH="${pkgs.libffi.dev}/lib/pkgconfig:${pkgs.zlib.dev}/lib/pkgconfig:${pkgs.libjpeg.dev}/lib/pkgconfig:$PKG_CONFIG_PATH"

    # Runtime library discovery for dynamically loaded shared objects (.so)
    export LD_LIBRARY_PATH="${pkgs.libffi}/lib:${pkgs.zlib}/lib:${pkgs.libjpeg}/lib:$LD_LIBRARY_PATH"
  '';
}
