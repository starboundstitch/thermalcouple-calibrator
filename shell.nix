{ pkgs ? import <nixpkgs> {} }:

with pkgs;

mkShell {
  buildInputs = [
    arduino-cli
    python311Packages.pyserial
  ];
}

