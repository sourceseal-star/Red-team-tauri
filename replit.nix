{ pkgs }: {
  deps = [
    pkgs.graalvmPackages.graalnodejs
    pkgs.python311Packages.pip
    pkgs.python311Packages.requests
    pkgs.python311Packages.pytz
  ];
}
