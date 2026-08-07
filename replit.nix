{ pkgs }: {
  deps = [
    pkgs.graalvmPackages.graalnodejs
    pkgs.python311Packages.pip
    pkgs.python311Packages.requests
    pkgs.python311Packages.pytz
    pkgs.python311Packages.fastapi
    pkgs.python311Packages.uvicorn
    pkgs.python311Packages.httpx
    pkgs.python311Packages.psutil
  ];
}
