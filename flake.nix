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

              nativeBuildInputs = with pkgs; [
                rustPlatform.maturinBuildHook
                rustPlatform.cargoSetupHook
              ];

              cargoDeps = pkgs.rustPlatform.fetchCargoVendor {
                inherit src;
                hash = "sha256-/dpxp+m/QakSxIP8t2dOtUK4Irac9C+ow5Jq1FlSTZE=";
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
