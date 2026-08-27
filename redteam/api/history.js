// Vercel serverless — devuelve histórico de reportes
const fs = require("fs");
const path = require("path");

module.exports = async (req, res) => {
  res.setHeader("Access-Control-Allow-Origin", process.env.ALLOWED_ORIGINS || "http://localhost:5173");
  res.setHeader("Cache-Control", "no-store");
  const reportsDir = path.join(process.cwd(), "reports");
  try {
    if (!fs.existsSync(reportsDir)) return res.status(200).json([]);
    const files = fs.readdirSync(reportsDir)
      .filter(f => f.startsWith("report-") && f.endsWith(".json"))
      .sort().reverse().slice(0, 50);
    const data = files.map(f => {
      try {
        const r = JSON.parse(fs.readFileSync(path.join(reportsDir, f), "utf8"));
        return { finished_at: r.finished_at, by_severity: r.by_severity, total_findings: r.total_findings };
      } catch { return null; }
    }).filter(Boolean).reverse();
    res.status(200).json(data);
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
};
