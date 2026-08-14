from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import requests
import socket

router = APIRouter(tags=["geo", "intel"])

@router.get("/api/geo")
async def geolocate(ip: str = Query(..., description="IP a geolocalizar")):
    """
    Geolocalizar IP usando ipapi.co (HTTPS gratuito, sin key requerida)
    Fallback a ip-api.com (HTTP) en entornos con acceso completo
    """
    # Validar que es una IP válida
    try:
        socket.inet_aton(ip)
    except (socket.error, OSError):
        raise HTTPException(status_code=400, detail="Invalid IP address")
    
    # Intentar primero con ipapi.co (HTTPS — funciona en sandboxes)
    try:
        response = requests.get(f"https://ipapi.co/{ip}/json/", timeout=10)
        data = response.json()
        
        if data.get('error'):
            raise HTTPException(status_code=404, detail=f"IP not found: {data.get('reason', 'unknown')}")
        
        return {
            "ip": data.get('ip') or ip,
            "country": data.get('country_name'),
            "countryCode": data.get('country_code'),
            "region": data.get('region'),
            "city": data.get('city'),
            "zip": data.get('postal'),
            "lat": data.get('latitude'),
            "lon": data.get('longitude'),
            "timezone": data.get('timezone'),
            "isp": data.get('org'),
            "org": data.get('org'),
            "as": data.get('asn'),
            "mobile": False,
            "proxy": False,
            "hosting": False,
            "source": "ipapi.co"
        }
    except requests.Timeout:
        pass  # Try fallback
    except requests.ConnectionError:
        pass  # Try fallback
    except HTTPException:
        raise
    except Exception:
        pass  # Try fallback
    
    # Fallback: ip-api.com (HTTP — funciona en Replit/Termux con acceso completo)
    try:
        response = requests.get(f"http://ip-api.com/json/{ip}", timeout=10)
        data = response.json()
        
        if data.get('status') == 'fail':
            raise HTTPException(status_code=404, detail=f"IP not found: {data.get('message')}")
        
        return {
            "ip": data.get('query'),
            "country": data.get('country'),
            "countryCode": data.get('countryCode'),
            "region": data.get('regionName'),
            "city": data.get('city'),
            "zip": data.get('zip'),
            "lat": data.get('lat'),
            "lon": data.get('lon'),
            "timezone": data.get('timezone'),
            "isp": data.get('isp'),
            "org": data.get('org'),
            "as": data.get('as'),
            "mobile": data.get('mobile', False),
            "proxy": data.get('proxy', False),
            "hosting": data.get('hosting', False),
            "source": "ip-api.com"
        }
    except requests.Timeout:
        raise HTTPException(status_code=504, detail="Geolocation service timeout")
    except requests.ConnectionError:
        raise HTTPException(status_code=503, detail="Geolocation service unavailable. En Replit/Termux funcionara correctamente.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/api/intel")
async def threat_intelligence(ip: str = Query(..., description="IP para threat intel")):
    """
    Threat Intelligence - Verificar si una IP es maliciosa
    Usa RBL lists (DNS) + ipapi.co para geolocation
    """
    # Validar IP
    try:
        socket.inet_aton(ip)
    except (socket.error, OSError):
        raise HTTPException(status_code=400, detail="Invalid IP address")
    
    results = {
        "ip": ip,
        "malicious": False,
        "score": 0,  # 0-100 (0 = limpio, 100 = muy malicioso)
        "reports": 0,
        "sources": {},
        "last_seen": None
    }
    
    # 1. Verificar en listas negras DNS (RBL) — funciona localmente
    rbl_lists = [
        "zen.spamhaus.org",
        "b.barracudacentral.org",
        "bl.spamcop.net"
    ]
    
    ip_parts = ip.split('.')
    reversed_ip = '.'.join(reversed(ip_parts))
    
    for rbl in rbl_lists:
        try:
            query = f"{reversed_ip}.{rbl}"
            socket.gethostbyname(query)
            results["sources"][rbl] = "LISTED"
            results["malicious"] = True
            results["score"] += 30
            results["reports"] += 1
        except socket.gaierror:
            results["sources"][rbl] = "clean"
        except Exception:
            results["sources"][rbl] = "unavailable"
    
    # 2. Verificar si es IP de hosting/cloud/proxy via ipapi.co (HTTPS)
    try:
        geo_response = requests.get(f"https://ipapi.co/{ip}/json/", timeout=5)
        geo_data = geo_response.json()
        
        if not geo_data.get('error'):
            results["isp"] = geo_data.get('org', '')
            results["country"] = geo_data.get('country_name', '')
            results["asn"] = geo_data.get('asn', '')
            
            # Si el ASN indica hosting, aumentar score
            org_lower = (geo_data.get('org', '') or '').lower()
            hosting_keywords = ['hosting', 'cloud', 'datacenter', 'server', 'ovh', 'digitalocean',
                               'amazon', 'aws', 'google', 'azure', 'linode', 'vultr', 'hetzner']
            if any(kw in org_lower for kw in hosting_keywords):
                results["score"] += 20
                results["sources"]["hosting_provider"] = True
            
            # Si parece VPN/proxy por el org name
            vpn_keywords = ['vpn', 'proxy', 'tor', 'tunnel', 'anonymous']
            if any(kw in org_lower for kw in vpn_keywords):
                results["score"] += 25
                results["sources"]["proxy_vpn"] = True
            
            results["last_seen"] = geo_data.get('timezone')
    except Exception:
        # Sin acceso a geo API — las RBL lists siguen funcionando
        results["sources"]["geo_lookup"] = "unavailable"
    
    # Determinar si es malicioso (score > 50)
    results["malicious"] = results["score"] >= 50
    
    return results


@router.get("/api/geo+intel")
async def geo_and_intel(ip: str = Query(..., description="IP para geo+intel")):
    """
    Combinar geolocalización + threat intelligence en una sola llamada
    """
    geo = await geolocate(ip)
    intel = await threat_intelligence(ip)
    
    return {
        **geo,
        "threat_intel": {
            "malicious": intel["malicious"],
            "score": intel["score"],
            "reports": intel["reports"],
            "sources": intel["sources"]
        }
    }
