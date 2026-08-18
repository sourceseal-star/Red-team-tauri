# ============================================================
# NOVOS ENDPOINTS OSINT ENGINE
# ============================================================

DISPOSABLE_DOMAINS = {
    "mailinator.com", "tempmail.com", "10minutemail.com", "guerrillamail.com",
    "throwawaymail.com", "yopmail.com", "trashmail.com", "sharklasers.com",
    "getnada.com", "dispostable.com", "tempail.com", "guerrillamailblock.com"
}

SOCIAL_PLATFORMS = [
    ("GitHub", "https://github.com/{}"),
    ("Twitter/X", "https://x.com/{}"),
    ("Instagram", "https://instagram.com/{}"),
    ("YouTube", "https://youtube.com/@{}"),
    ("TikTok", "https://tiktok.com/@{}"),
    ("Reddit", "https://reddit.com/user/{}"),
    ("GitLab", "https://gitlab.com/{}"),
    ("Medium", "https://medium.com/@{}"),
    ("Steam", "https://steamcommunity.com/id/{}"),
]

def _parse_rdn_tuple(rdn):
    if not rdn:
        return {}
    res = {}
    for r in rdn:
        for k, v in r:
            res[k] = v
    return res

async def _helper_get_ssl_cert(domain: str, port: int = 443) -> dict:
    loop = asyncio.get_running_loop()
    ctx = ssl.create_default_context()

    def _fetch_verified():
        with socket.create_connection((domain, port), timeout=5) as sock:
            with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                return ssock.getpeercert()

    try:
        cert = await loop.run_in_executor(None, _fetch_verified)
        issuer = _parse_rdn_tuple(cert.get("issuer", ()))
        subject = _parse_rdn_tuple(cert.get("subject", ()))
        is_self_signed = (issuer == subject) if (issuer and subject) else False
        return {
            "domain": domain,
            "port": port,
            "issuer": issuer,
            "subject": subject,
            "notBefore": cert.get("notBefore"),
            "notAfter": cert.get("notAfter"),
            "serialNumber": cert.get("serialNumber"),
            "version": cert.get("version"),
            "self_signed": is_self_signed,
            "verified": True,
            "error": None
        }
    except Exception as err:
        try:
            def _fetch_pem():
                return ssl.get_server_certificate((domain, port), timeout=5)

            pem = await loop.run_in_executor(None, _fetch_pem)
            proc = await asyncio.create_subprocess_exec(
                "openssl", "x509", "-noout", "-issuer", "-subject", "-dates", "-serial",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(input=pem.encode()), timeout=5)
            out_str = stdout.decode()

            parsed = {}
            for line in out_str.splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    parsed[k.strip().lower()] = v.strip()

            issuer_str = parsed.get("issuer", "")
            subject_str = parsed.get("subject", "")
            is_self = (issuer_str == subject_str) if (issuer_str and subject_str) else True

            return {
                "domain": domain,
                "port": port,
                "issuer": issuer_str,
                "subject": subject_str,
                "notBefore": parsed.get("notbefore"),
                "notAfter": parsed.get("notafter"),
                "serialNumber": parsed.get("serial"),
                "version": None,
                "self_signed": is_self,
                "verified": False,
                "error": str(err)
            }
        except Exception:
            return {
                "domain": domain,
                "port": port,
                "issuer": None,
                "subject": None,
                "notBefore": None,
                "notAfter": None,
                "serialNumber": None,
                "version": None,
                "self_signed": None,
                "verified": False,
                "error": str(err)
            }

def _detect_technologies(headers: dict) -> list:
    techs = []
    headers_lower = {str(k).lower(): str(v) for k, v in headers.items()}

    server = headers_lower.get("server", "")
    if server:
        techs.append(f"Server: {server}")

    x_powered_by = headers_lower.get("x-powered-by", "")
    if x_powered_by:
        techs.append(f"X-Powered-By: {x_powered_by}")

    x_aspnet = headers_lower.get("x-aspnet-version") or headers_lower.get("x-aspnetmvc-version")
    if x_aspnet:
        techs.append(f"ASP.NET ({x_aspnet})")

    x_gen = headers_lower.get("x-generator", "")
    if x_gen:
        techs.append(f"Generator: {x_gen}")

    if "cf-ray" in headers_lower or "cloudflare" in server.lower() or "cf-cache-status" in headers_lower:
        techs.append("Cloudflare")

    if "x-varnish" in headers_lower or "varnish" in headers_lower.get("via", "").lower():
        techs.append("Varnish Cache")

    if "x-github-request-id" in headers_lower:
        techs.append("GitHub Pages")

    cookies = headers_lower.get("set-cookie", "")
    if "phpsessid" in cookies.lower():
        techs.append("PHP")
    if "jsessionid" in cookies.lower():
        techs.append("Java/Servlet")
    if "asp.net_sessionid" in cookies.lower() or "aspsessionid" in cookies.lower():
        techs.append("ASP.NET")
    if "laravel_session" in cookies.lower():
        techs.append("Laravel")
    if "wordpress_" in cookies.lower() or "wp-settings-" in cookies.lower():
        techs.append("WordPress")
    if "csrftoken" in cookies.lower():
        techs.append("Django")

    return list(dict.fromkeys(techs))


@app.get("/api/osint/dns/{domain}")
async def osint_dns(domain: str):
    cached = _osint_get_cache(domain, "dns")
    if cached:
        return cached[0]

    record_types = ["A", "AAAA", "MX", "TXT", "NS", "CNAME", "SOA"]
    records = {}

    async def fetch_record(rtype: str):
        try:
            proc = await asyncio.create_subprocess_exec(
                "dig", "+short", rtype, domain,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
            lines = [l.strip() for l in stdout.decode().splitlines() if l.strip() and not l.strip().startswith(";")]
            return rtype, lines
        except FileNotFoundError:
            raise FileNotFoundError("dig_not_installed")
        except Exception:
            return rtype, []

    try:
        results = await asyncio.gather(*[fetch_record(rt) for rt in record_types])
        for rtype, lines in results:
            records[rtype] = lines
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="dig no instalado. Instala: pkg install bind-tools (Termux) o apt install bind9-dnsutils (Linux)"
        )

    result = {
        "domain": domain,
        "records": records,
        "timestamp": datetime.now().isoformat()
    }
    _osint_cache_result(domain, "dns", result)
    return result


@app.get("/api/osint/headers/{domain}")
async def osint_headers(domain: str):
    cached = _osint_get_cache(domain, "headers")
    if cached:
        return cached[0]

    headers = {}
    status_code = None
    url_used = None
    error = None

    for scheme in ["https", "http"]:
        target_url = f"{scheme}://{domain}"
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=10.0, verify=False) as client:
                resp = await client.get(target_url)
                headers = dict(resp.headers)
                status_code = resp.status_code
                url_used = str(resp.url)
                break
        except Exception as e:
            error = str(e)

    tls_info = None
    try:
        tls_info = await _helper_get_ssl_cert(domain, 443)
    except Exception as e:
        tls_info = {"error": str(e)}

    technologies = _detect_technologies(headers)

    result = {
        "domain": domain,
        "url": url_used,
        "status_code": status_code,
        "headers": headers,
        "technologies": technologies,
        "tls": tls_info,
        "error": error if not headers else None,
        "timestamp": datetime.now().isoformat()
    }

    _osint_cache_result(domain, "headers", result)
    return result


@app.get("/api/osint/reverse/{ip}")
async def osint_reverse(ip: str):
    if not _valid_ip(ip):
        raise HTTPException(status_code=400, detail="Dirección IP inválida")

    cached = _osint_get_cache(ip, "reverse")
    if cached:
        return cached[0]

    loop = asyncio.get_running_loop()

    hostname = None
    aliases = []
    try:
        res = await loop.run_in_executor(None, socket.gethostbyaddr, ip)
        hostname = res[0]
        aliases = res[1]
    except Exception:
        hostname = None

    geo_data = {}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"https://ipwho.is/{ip}")
            if resp.status_code == 200:
                geo_data = resp.json()
    except Exception as e:
        geo_data = {"error": str(e)}

    result = {
        "ip": ip,
        "hostname": hostname,
        "aliases": aliases,
        "geo": geo_data,
        "timestamp": datetime.now().isoformat()
    }

    _osint_cache_result(ip, "reverse", result)
    return result


@app.get("/api/osint/breach/{email}")
async def osint_breach(email: str):
    cached = _osint_get_cache(email, "breach")
    if cached:
        return cached[0]

    email_pattern = r"^[^@\s]+@([^@\s]+\.[^@\s]+)$"
    match = re.match(email_pattern, email)
    valid_format = bool(match)
    domain = match.group(1).lower() if match else ""

    is_disposable = domain in DISPOSABLE_DOMAINS if domain else False

    mx_records = []
    if domain:
        try:
            proc = await asyncio.create_subprocess_exec(
                "dig", "+short", "MX", domain,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
            mx_records = [l.strip() for l in stdout.decode().splitlines() if l.strip() and not l.strip().startswith(";")]
        except Exception:
            mx_records = []

    breaches = []
    status_note = "Local validation + MX verification completed."

    headers = {"User-Agent": "RedTeam-Dashboard-OSINT/1.0"}
    async with httpx.AsyncClient(timeout=8.0, headers=headers) as client:
        try:
            resp = await client.get(f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}")
            if resp.status_code == 200:
                breaches = resp.json()
                status_note = "Breaches retrieved from HaveIBeenPwned."
            elif resp.status_code in (401, 403):
                status_note = "HaveIBeenPwned requires API key. Tried free fallback API."
        except Exception:
            pass

        if not breaches:
            try:
                resp = await client.get(f"https://leakcheck.io/api/public?check={email}")
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("success"):
                        breaches = data.get("sources", [])
                        status_note = "Breach data retrieved from LeakCheck free API."
            except Exception:
                pass

        if not breaches and "HaveIBeenPwned" not in status_note and "LeakCheck" not in status_note:
            try:
                resp = await client.get(f"https://api.dehash.lt/api/search?email={email}")
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list):
                        breaches = data
                        status_note = "Breach data retrieved from DeHash API."
                    elif isinstance(data, dict) and data.get("results"):
                        breaches = data.get("results")
                        status_note = "Breach data retrieved from DeHash API."
            except Exception:
                pass

    result = {
        "email": email,
        "valid_format": valid_format,
        "domain": domain,
        "disposable": is_disposable,
        "mx_records": mx_records,
        "breaches": breaches,
        "status_note": status_note,
        "timestamp": datetime.now().isoformat()
    }

    _osint_cache_result(email, "breach", result)
    return result


@app.get("/api/osint/social/{username}")
async def osint_social(username: str):
    cached = _osint_get_cache(username, "social")
    if cached:
        return cached[0]

    semaphore = asyncio.Semaphore(5)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    async def check_platform(client, platform_name: str, url_tmpl: str):
        url = url_tmpl.format(username)
        async with semaphore:
            try:
                resp = await client.get(url)
                status_code = resp.status_code
                exists = (200 <= status_code < 300)
                return {
                    "platform": platform_name,
                    "url": url,
                    "exists": exists,
                    "status_code": status_code
                }
            except Exception as e:
                return {
                    "platform": platform_name,
                    "url": url,
                    "exists": False,
                    "status_code": None,
                    "error": str(e)
                }

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers=headers) as client:
        results = await asyncio.gather(
            *[check_platform(client, p, u) for p, u in SOCIAL_PLATFORMS]
        )

    total_found = sum(1 for r in results if r.get("exists"))
    result = {
        "username": username,
        "results": results,
        "total_found": total_found,
        "timestamp": datetime.now().isoformat()
    }

    _osint_cache_result(username, "social", result)
    return result


@app.get("/api/osint/cert/{domain}")
async def osint_cert(domain: str):
    cached = _osint_get_cache(domain, "cert")
    if cached:
        return cached[0]

    result = await _helper_get_ssl_cert(domain, 443)
    result["timestamp"] = datetime.now().isoformat()

    _osint_cache_result(domain, "cert", result)
    return result


@app.get("/api/osint/full/{target}")
async def osint_full(target: str):
    cached = _osint_get_cache(target, "full")
    if cached:
        return cached[0]

    is_ip = _valid_ip(target)

    if is_ip:
        async def _rdns_task(ip):
            loop = asyncio.get_running_loop()
            try:
                res = await loop.run_in_executor(None, socket.gethostbyaddr, ip)
                return {"hostname": res[0], "aliases": res[1]}
            except Exception as e:
                return {"hostname": None, "error": str(e)}

        async def _geo_task(ip):
            try:
                async with httpx.AsyncClient(timeout=8.0) as client:
                    resp = await client.get(f"https://ipwho.is/{ip}")
                    if resp.status_code == 200:
                        return resp.json()
            except Exception as e:
                return {"error": str(e)}
            return {}

        async def _threat_task(ip):
            threat_data = {"ip": ip, "is_private": False, "flags": [], "risk_score": 0}
            try:
                ip_obj = ipaddress.ip_address(ip)
                if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_reserved:
                    threat_data["is_private"] = True
                    threat_data["flags"].append("internal/private_ip")
                    threat_data["risk_score"] = 0
                    return threat_data
            except Exception:
                pass

            try:
                async with httpx.AsyncClient(timeout=8.0) as client:
                    resp = await client.get(f"https://ipwho.is/{ip}")
                    if resp.status_code == 200:
                        data = resp.json()
                        security = data.get("security", {})
                        if security.get("vpn"):
                            threat_data["flags"].append("vpn")
                            threat_data["risk_score"] += 20
                        if security.get("proxy"):
                            threat_data["flags"].append("proxy")
                            threat_data["risk_score"] += 30
                        if security.get("tor"):
                            threat_data["flags"].append("tor")
                            threat_data["risk_score"] += 50
                        if security.get("hosting"):
                            threat_data["flags"].append("datacenter/hosting")
                            threat_data["risk_score"] += 10
            except Exception as e:
                threat_data["error"] = str(e)

            return threat_data

        rdns_res, geo_res, threat_res = await asyncio.gather(
            _rdns_task(target),
            _geo_task(target),
            _threat_task(target)
        )

        full_report = {
            "target": target,
            "target_type": "ip",
            "timestamp": datetime.now().isoformat(),
            "rdns": rdns_res,
            "geo": geo_res,
            "threat_intel": threat_res
        }
    else:
        async def _whois_task(domain):
            try:
                proc = await asyncio.create_subprocess_exec(
                    "whois", domain,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
                output = stdout.decode()
                parsed = {}
                for line in output.split("\n"):
                    if ":" in line and not line.startswith("%"):
                        k, v = line.split(":", 1)
                        k = k.strip()
                        v = v.strip()
                        if k and v and k not in parsed:
                            parsed[k] = v
                return {"raw": output[:3000], "parsed": parsed}
            except Exception as e:
                return {"error": str(e)}

        async def _subdomains_task(domain):
            try:
                return await _fetch_crtsh(domain)
            except Exception as e:
                return [{"error": str(e)}]

        async def _dns_task(domain):
            record_types = ["A", "AAAA", "MX", "TXT", "NS", "CNAME", "SOA"]
            records = {}

            async def fetch_record(rt):
                try:
                    proc = await asyncio.create_subprocess_exec(
                        "dig", "+short", rt, domain,
                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                    )
                    stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
                    lines = [l.strip() for l in stdout.decode().splitlines() if l.strip() and not l.strip().startswith(";")]
                    return rt, lines
                except Exception:
                    return rt, []

            results = await asyncio.gather(*[fetch_record(rt) for rt in record_types])
            for rt, lines in results:
                records[rt] = lines
            return records

        async def _headers_task(domain):
            headers = {}
            status_code = None
            url_used = None
            for scheme in ["https", "http"]:
                try:
                    async with httpx.AsyncClient(follow_redirects=True, timeout=8.0, verify=False) as client:
                        resp = await client.get(f"{scheme}://{domain}")
                        headers = dict(resp.headers)
                        status_code = resp.status_code
                        url_used = str(resp.url)
                        break
                except Exception:
                    pass
            techs = _detect_technologies(headers)
            return {"url": url_used, "status_code": status_code, "headers": headers, "technologies": techs}

        async def _cert_task(domain):
            try:
                return await _helper_get_ssl_cert(domain, 443)
            except Exception as e:
                return {"error": str(e)}

        whois_res, subdomains_res, dns_res, headers_res, cert_res = await asyncio.gather(
            _whois_task(target),
            _subdomains_task(target),
            _dns_task(target),
            _headers_task(target),
            _cert_task(target)
        )

        full_report = {
            "target": target,
            "target_type": "domain",
            "timestamp": datetime.now().isoformat(),
            "whois": whois_res,
            "subdomains": subdomains_res,
            "dns": dns_res,
            "headers": headers_res,
            "cert": cert_res
        }

    _osint_cache_result(target, "full", full_report)
    return full_report


@app.get("/api/osint/export/{target}")
async def osint_export(target: str):
    cached = _osint_get_cache(target, "full")
    if cached:
        report = cached[0]
    else:
        report = await osint_full(target)

    return JSONResponse(
        content=report,
        headers={"Content-Disposition": f'attachment; filename="osint_report_{target}.json"'}
    )
