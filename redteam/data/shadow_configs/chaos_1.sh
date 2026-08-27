#!/bin/bash
# Chaos Fingerprint Rule 1
# Puerto real: 22 -> Responde como: Windows / Microsoft-IIS/10.0

iptables -t nat -A PREROUTING -p tcp --dport 22 -j REDIRECT --to-port 20022

while true; do
    echo -e "HTTP/1.1 200 OK\r\nServer: Microsoft-IIS/10.0\r\nX-Powered-By: ASP.NET\r\n\r\n<html><body>IIS Windows Server</body></html>" | nc -l -p 20022
done &
