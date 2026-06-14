{
  inputs = {
    flake-parts.url = "github:hercules-ci/flake-parts";
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
  };

  outputs = inputs:
    inputs.flake-parts.lib.mkFlake
      { inherit inputs; }
      {
        systems = [ "x86_64-linux" ];

        perSystem = { pkgs, ... }:
          let
            pyrage = pkgs.python3Packages.buildPythonPackage rec {
              pname = "pyrage";
              version = "1.3.0";
              pyproject = true;

              src = pkgs.fetchPypi {
                inherit pname version;
                hash = "sha256-soOi49aIy/aMcH9X2T/aszBP9Xx+LmtxDAtLyQlq2do=";
              };

              # pyrage is a maturin/PyO3 package — needs Rust build infrastructure
              nativeBuildInputs = with pkgs; [
                rustPlatform.maturinBuildHook
                rustPlatform.cargoSetupHook
                cargo
                rustc
              ];

              cargoDeps = pkgs.rustPlatform.fetchCargoVendor {
                inherit src;
                # Run `nix build` once with hash = pkgs.lib.fakeHash, then
                # replace this with the hash printed in the error message.
                hash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
              };
            };
          in
          {
            devShells.default = pkgs.mkShell {
              packages = with pkgs; [
                ruff
                pyright

                (python3.withPackages (ps: with ps; [
                  click
                  cryptography
                  jinja2
                  requests
                  tomli-w
                  pyrage
                ]))
              ];
            };
          };
      };
}
