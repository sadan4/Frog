{
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      platforms = [ "aarch64-linux" "i686-linux" "x86_64-linux" ];
      pkgs = (import nixpkgs { });
      packages = builtins.listToAttrs
        (
          builtins.map
            (e:
              let
                pkgs = import nixpkgs { system = e; };
              in
              {
                name = e;
                value = {
                  default = pkgs.callPackage ./. { };
                };
              })
            platforms
        );
    in
    {
      inherit packages;
    };
}
