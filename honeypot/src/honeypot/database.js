const sqlite3 = require('sqlite3').verbose();
const path = require('path');
const fs = require('fs');

const DB_PATH = process.env.HONEYPOT_DB || path.join(__dirname, '..', '..', 'data', 'honeypot.db');

// Ensure data dir exists
const dbDir = path.dirname(DB_PATH);
if (!fs.existsSync(dbDir)) fs.mkdirSync(dbDir, { recursive: true });

const db = new sqlite3.Database(DB_PATH);

// Initialize schema
db.serialize(() => {
  db.run(`CREATE TABLE IF NOT EXISTS honeypot_attacks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT NOT NULL,
    ip_address TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    method TEXT,
    path TEXT,
    user_agent TEXT,
    headers TEXT,
    payload TEXT,
    severity TEXT,
    country TEXT,
    processed BOOLEAN DEFAULT FALSE
  )`);

  db.run(`CREATE INDEX IF NOT EXISTS idx_attacks_ip ON honeypot_attacks(ip_address)`);
  db.run(`CREATE INDEX IF NOT EXISTS idx_attacks_token ON honeypot_attacks(token)`);
  db.run(`CREATE INDEX IF NOT EXISTS idx_attacks_timestamp ON honeypot_attacks(timestamp)`);
  db.run(`CREATE INDEX IF NOT EXISTS idx_attacks_severity ON honeypot_attacks(severity)`);
});

function insertAttack(attack) {
  return new Promise((resolve, reject) => {
    db.run(
      `INSERT INTO honeypot_attacks (token, ip_address, method, path, user_agent, headers, payload, severity, country)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [attack.token, attack.ip_address, attack.method, attack.path,
       attack.user_agent, attack.headers, attack.payload, attack.severity, attack.country],
      function(err) {
        if (err) reject(err);
        else resolve({ id: this.lastID, ...attack });
      }
    );
  });
}

function getAttacks(token, limit = 100, offset = 0) {
  return new Promise((resolve, reject) => {
    db.all(
      `SELECT * FROM honeypot_attacks WHERE token = ? ORDER BY timestamp DESC LIMIT ? OFFSET ?`,
      [token, limit, offset],
      (err, rows) => err ? reject(err) : resolve(rows)
    );
  });
}

function getTopIPs(hours = 24, limit = 20) {
  return new Promise((resolve, reject) => {
    db.all(
      `SELECT ip_address, COUNT(*) as count, 
              GROUP_CONCAT(DISTINCT path) as paths,
              GROUP_CONCAT(DISTINCT severity) as severities,
              MAX(timestamp) as last_seen
       FROM honeypot_attacks 
       WHERE timestamp >= datetime('now', ?)
       GROUP BY ip_address 
       ORDER BY count DESC LIMIT ?`,
      [`-${hours} hours`, limit],
      (err, rows) => err ? reject(err) : resolve(rows)
    );
  });
}

function getStats(token) {
  return new Promise((resolve, reject) => {
    const query = token
      ? `WHERE token = ?`
      : `WHERE 1=1`;
    const params = token ? [token] : [];

    db.get(
      `SELECT COUNT(*) as total_attacks,
              COUNT(DISTINCT ip_address) as unique_ips,
              COUNT(CASE WHEN severity='critical' THEN 1 END) as critical,
              COUNT(CASE WHEN severity='high' THEN 1 END) as high,
              COUNT(CASE WHEN severity='medium' THEN 1 END) as medium,
              COUNT(CASE WHEN severity='low' THEN 1 END) as low
       FROM honeypot_attacks ${query}`,
      params,
      (err, row) => {
        if (err) return reject(err);
        
        // Top paths
        db.all(
          `SELECT path, COUNT(*) as count FROM honeypot_attacks ${query} GROUP BY path ORDER BY count DESC LIMIT 10`,
          params,
          (err2, paths) => {
            if (err2) return reject(err2);
            
            // Timeline (last 24h, hourly)
            db.all(
              `SELECT strftime('%Y-%m-%d %H:00:00', timestamp) as hour, COUNT(*) as count
               FROM honeypot_attacks ${query}
               AND timestamp >= datetime('now', '-24 hours')
               GROUP BY hour ORDER BY hour`,
              params,
              (err3, timeline) => {
                if (err3) return reject(err3);
                resolve({
                  ...row,
                  top_paths: paths,
                  timeline: timeline
                });
              }
            );
          }
        );
      }
    );
  });
}

function getByCountry(token) {
  return new Promise((resolve, reject) => {
    const query = token ? `WHERE token = ?` : ``;
    const params = token ? [token] : [];
    db.all(
      `SELECT country, COUNT(*) as count, COUNT(DISTINCT ip_address) as unique_ips
       FROM honeypot_attacks ${query}
       GROUP BY country ORDER BY count DESC`,
      params,
      (err, rows) => err ? reject(err) : resolve(rows)
    );
  });
}

function exportAttacks(token, format = 'json') {
  return new Promise((resolve, reject) => {
    db.all(
      `SELECT * FROM honeypot_attacks WHERE token = ? ORDER BY timestamp DESC`,
      [token],
      (err, rows) => {
        if (err) return reject(err);
        if (format === 'csv') {
          if (rows.length === 0) return resolve('id,token,ip_address,timestamp,method,path,user_agent,severity,country\n');
          const headers = ['id','token','ip_address','timestamp','method','path','user_agent','severity','country'];
          let csv = headers.join(',') + '\n';
          for (const r of rows) {
            csv += [
              r.id, r.token, r.ip_address, r.timestamp,
              r.method, r.path, `"${(r.user_agent||'').replace(/"/g,'""')}"`,
              r.severity, r.country||'Unknown'
            ].join(',') + '\n';
          }
          resolve(csv);
        } else if (format === 'txt') {
          if (rows.length === 0) return resolve('No attacks found.\n');
          let txt = '';
          for (const r of rows) {
            txt += `[${r.timestamp}] ${r.ip_address} (${r.country||'?'}) ${r.method} ${r.path} [${r.severity}]\n`;
            txt += `  UA: ${(r.user_agent||'').substring(0,80)}\n\n`;
          }
          resolve(txt);
        }
        resolve(JSON.stringify(rows, null, 2));
      }
    );
  });
}

function clearAttacks(token) {
  return new Promise((resolve, reject) => {
    db.run(
      token ? `DELETE FROM honeypot_attacks WHERE token = ?` : `DELETE FROM honeypot_attacks`,
      token ? [token] : [],
      function(err) {
        if (err) reject(err);
        else resolve({ deleted: this.changes });
      }
    );
  });
}

module.exports = {
  db, insertAttack, getAttacks, getTopIPs, getStats,
  getByCountry, exportAttacks, clearAttacks
};
