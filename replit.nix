{ pkgs }: {
  deps = [
    pkgs.graalvmPackages.graalnodejs
    pkgs.nmap
    pkgs.python312Packages.pip
    pkgs.python312Packages.requests
    pkgs.python312Packages.pytz
    pkgs.python312Packages.fastapi
    pkgs.python312Packages.uvicorn
    pkgs.python312Packages.pydantic
    pkgs.python312Packages.httpx
    pkgs.python312Packages.psutil
    pkgs.python312Packages.dnspython
    pkgs.python312Packages.beautifulsoup4
    pkgs.python312Packages.python-whois
  ];
}
