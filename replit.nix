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
    pkgs.python312Packages.aiohttp
    pkgs.python312Packages.numpy
    pkgs.python312Packages.qrcode
    pkgs.python312Packages.reportlab
    pkgs.python312Packages.cryptography
    pkgs.python312Packages.pillow
    pkgs.python312Packages.onnxruntime
    pkgs.python312Packages.pyyaml
  ];
}
