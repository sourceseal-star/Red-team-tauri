// Vercel serverless — ejecuta el orchestrator
// NOTA: Vercel tiene timeout de 10s en hobby / 60s en pro.
// Para escaneos largos, usa el agente en Docker/Replit.
const { spawn } = require("child_process");
const path = require("path");

module.exports = async (req, res) => {
  res.setHeader("Access-Control-Allow-Origin", process.env.ALLOWED_ORIGINS || "http://localhost:5173");
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Use POST" });
  }
  const started = Date.now();
  try {
    const root = process.cwd();
    const evidence = path.join(root, "evidence");
    const target = path.join(evidence, "dummy.apk");
    // Crear dummy si no existe
    const fs = require("fs");
    if (!fs.existsSync(evidence)) fs.mkdirSync(evidence, { recursive: true });
    if (!fs.existsSync(target)) fs.writeFileSync(target, "");

    const py = spawn("python3", [
      path.join(root, "runner/orchestrator.py"),
      "--target", target,
      "--backend", process.env.SOURCESEAL_API || "https://api.sourcesealcorp.local",
      "--output", path.join(root, "reports"),
    ], { cwd: root, timeout: 55000 });

    let stderr = "";
    py.stderr.on("data", d => stderr += d.toString());
    py.on("close", code => {
      const elapsed = ((Date.now() - started) / 1000).toFixed(1);
      if (code !== 0) {
        return res.status(500).json({ ok: false, error: stderr.slice(-500), elapsed });
      }
      // leer último reporte
      const reportsDir = path.join(root, "reports");
      const files = fs.readdirSync(reportsDir)
        .filter(f => f.startsWith("report-") && f.endsWith(".json"))
        .sort().reverse();
      let findings = 0;
      if (files.length) {
        try {
          const r = JSON.parse(fs.readFileSync(path.join(reportsDir, files[0]), "utf8"));
          findings = r.total_findings || 0;
        } catch {}
      }
      res.status(200).json({ ok: true, findings, elapsed });
    });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
};
