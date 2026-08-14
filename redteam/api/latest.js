// Vercel serverless — devuelve el último reporte
const fs = require("fs");
const path = require("path");

module.exports = async (req, res) => {
  res.setHeader("Access-Control-Allow-Origin", process.env.ALLOWED_ORIGINS || "http://localhost:5173");
  res.setHeader("Cache-Control", "no-store");
  const reportsDir = path.join(process.cwd(), "reports");
  try {
    if (!fs.existsSync(reportsDir)) {
      return res.status(200).json({ findings: [], by_severity: {}, total_findings: 0, agent: "no-data" });
    }
    const files = fs.readdirSync(reportsDir)
      .filter(f => f.startsWith("report-") && f.endsWith(".json"))
      .sort().reverse();
    if (!files.length) {
      return res.status(200).json({ findings: [], by_severity: {}, total_findings: 0, agent: "empty" });
    }
    const data = JSON.parse(fs.readFileSync(path.join(reportsDir, files[0]), "utf8"));
    data.agent = data.agent || "redteam-agent";
    res.status(200).json(data);
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
};
