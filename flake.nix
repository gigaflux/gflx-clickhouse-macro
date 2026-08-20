{
  description = "A reproducible development environment";

  # Inputs define the dependencies this flake relies on
  inputs = {
    # Using the unstable branch of nixpkgs for the latest versions of uv and gh
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";

    # A utility library to easily generate outputs for multiple CPU architectures
    utils.url = "github:numtide/flake-utils";
  };

  # Outputs define the environment and packages provided by this flake
  outputs = { self, nixpkgs, utils }:
    # Automatically loop through standard systems (e.g., x86_64-linux, aarch64-darwin for M1-M4 Macs)
    utils.lib.eachDefaultSystem (system:
      let
        # Import the nixpkgs library configured for the current system architecture
        pkgs = import nixpkgs { inherit system; };
      in
      {
        # Define the default development shell activated via 'nix develop'
        devShells.default = pkgs.mkShell {
          # System packages that Nix will install and inject into the shell's PATH
          buildInputs = [
            pkgs.coreutils # GNU core utilities (ls, cat, cp, mv, etc.)
            pkgs.findutils # GNU find and xargs
            pkgs.gnutar # GNU tar
            pkgs.gnused   # GNU version of 'sed'
            pkgs.gnugrep  # GNU version of 'grep'
            pkgs.rsync # Rsync
            pkgs.gnumake  # GNU Make utility for processing the project's Makefile
            pkgs.git      # Git version control system
            pkgs.gh       # Official GitHub CLI tool for managing releases and pull requests
            pkgs.uv       # Extremely fast Python package installer and resolver
            pkgs.act      # Run your GitHub Actions workflows locally inside Docker containers
          ];

          # Bash commands executed automatically immediately upon entering the shell
          shellHook = ''
            echo "========================================================="
            echo -e "\u26A1 Welcome to development shell!"
            echo "========================================================="

            # Automatically initialize or sync the virtual environment using uv
            make init-dev
            echo -e "\u2713 Python virtual environment (.venv) successfully activated!"
            echo "========================================================="
          '';
        };
      });
}
