const SS_API = 'https://sourceseal.co/api'; // ajusta a tu endpoint real

export async function sealReport(payload: any) {
  // 1. Generar hash local
  const data = new TextEncoder().encode(JSON.stringify(payload));
  const buf = await crypto.subtle.digest('SHA-256', data);
  const hash = Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, '0')).join('');
  // 2. Enviar al anclaje
  const res = await fetch(`${SS_API}/seal`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ hash, ts: Date.now(), type: 'red-team-report' }),
  });
  return { hash, anchor: await res.json() };
}

// Helper: sellar y descargar reporte como JSON sellado
export async function sealAndExport(payload: any, filename: string = 'redteam-report.json') {
  const { hash, anchor } = await sealReport(payload);
  const sealed = {
    protocol: 'SourceSeal Global Protocol v2.1',
    sealedAt: new Date().toISOString(),
    contentHash: hash,
    anchor,
    payload,
  };
  const blob = new Blob([JSON.stringify(sealed, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
  return sealed;
}
