#!/bin/sh
# Honeytramp entrypoint — arranca C2 sinkhole y DNS sinkhole en paralelo
cd /honeypot
python3 c2-sinkhole/sinkhole.py &
C2_PID=$!
python3 c2-sinkhole/dns_sinkhole.py &
DNS_PID=$!
trap "kill $C2_PID $DNS_PID 2>/dev/null" EXIT
wait
