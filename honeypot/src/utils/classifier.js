/**
 * Clasificador de severidad automático
 * Basado en el path solicitado, payload y patrones de ataque
 */

const SEVERITY_RULES = [
  // CRITICAL — acceso a datos sensibles / admin
  { severity: 'critical', patterns: [/\/admin/i, /\/wp-admin/i, /\/\.env/i, /\/\.git/i, /\/backup/i, /\/phpmyadmin/i, /\/shell/i, /\/cmd/i, /\/config\.php/i] },
  
  // HIGH — inyecciones y traversal
  { severity: 'high', patterns: [/union\s+select/i, /or\s+1=1/i, /drop\s+table/i, /<script/i, /javascript:/i, /\.\.\/\.\.\//i, /\/etc\/passwd/i, /exec\(/i, /eval\(/i, /base64_decode/i] },
  
  // MEDIUM — reconnaissance
  { severity: 'medium', patterns: [/\/wp-login/i, /\/xmlrpc\.php/i, /\/wp-content/i, /\/api\/v1\/users/i, /\/api\/admin/i, /sqlmap/i, /nikto/i, /nmap/i, /masscan/i, /dirbuster/i] },
  
  // LOW — generic probes
  { severity: 'low', patterns: [/\/favicon/i, /\/robots\.txt/i, /\.well-known/i] },
];

const HIGH_PATTERNS = [
  { pattern: /union\s+select/i, name: 'SQL Injection (UNION)' },
  { pattern: /or\s+1\s*=\s*1/i, name: 'SQL Injection (OR 1=1)' },
  { pattern: /drop\s+table/i, name: 'SQL Injection (DROP)' },
  { pattern: /<script[^>]*>/i, name: 'XSS (script tag)' },
  { pattern: /javascript:/i, name: 'XSS (javascript:)' },
  { pattern: /\.\.\/\.\.\//i, name: 'Path Traversal' },
  { pattern: /\/etc\/passwd/i, name: 'Path Traversal (/etc/passwd)' },
  { pattern: /exec\s*\(/i, name: 'Code Injection (exec)' },
  { pattern: /eval\s*\(/i, name: 'Code Injection (eval)' },
  { pattern: /base64_decode/i, name: 'Base64 Decode Attack' },
  { pattern: /shell_exec/i, name: 'Shell Execution' },
];

const CRITICAL_PATHS = [
  '/admin', '/wp-admin', '/.env', '/.git/config', '/backup.sql',
  '/phpmyadmin', '/shell', '/cmd', '/config.php'
];

function classify(method, path, payload, userAgent) {
  const fullPath = (path || '').toLowerCase();
  const payloadStr = (payload || '').toLowerCase();
  const uaStr = (userAgent || '').toLowerCase();

  // Check critical paths first
  for (const cp of CRITICAL_PATHS) {
    if (fullPath.includes(cp)) {
      let attackType = 'Critical Path Access';
      if (cp === '/.env') attackType = 'Environment File Access';
      if (cp === '/.git/config') attackType = 'Git Repository Access';
      if (cp === '/backup.sql') attackType = 'Database Backup Access';
      if (cp === '/phpmyadmin') attackType = 'phpMyAdmin Access';
      if (cp === '/admin' || cp === '/wp-admin') attackType = 'Admin Panel Access';
      return { severity: 'critical', attack_type: attackType };
    }
  }

  // Check HIGH patterns (SQL injection, XSS, traversal, RCE)
  for (const p of HIGH_PATTERNS) {
    if (p.pattern.test(fullPath) || p.pattern.test(payloadStr)) {
      return { severity: 'high', attack_type: p.name };
    }
  }

  // Check reconnaissance tools in User-Agent
  if (/sqlmap|nikto|nmap|masscan|dirbuster|gobuster|wpscan|hydra/i.test(uaStr)) {
    return { severity: 'medium', attack_type: 'Reconnaissance Tool' };
  }

  // Check medium patterns
  for (const rule of SEVERITY_RULES) {
    if (rule.severity === 'medium') {
      for (const p of rule.patterns) {
        if (p.test(fullPath)) {
          return { severity: 'medium', attack_type: 'Reconnaissance' };
        }
      }
    }
  }

  // Check low patterns
  for (const rule of SEVERITY_RULES) {
    if (rule.severity === 'low') {
      for (const p of rule.patterns) {
        if (p.test(fullPath)) {
          return { severity: 'low', attack_type: 'Generic Probe' };
        }
      }
    }

  }

  // POST requests to unusual paths are at least medium
  if (method === 'POST' && !fullPath.startsWith('/api/')) {
    return { severity: 'medium', attack_type: 'Suspicious POST' };
  }

  // Default — low probe
  return { severity: 'low', attack_type: 'Generic Probe' };
}

module.exports = { classify, SEVERITY_RULES, CRITICAL_PATHS, HIGH_PATTERNS };
