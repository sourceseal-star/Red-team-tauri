import React, { useState, useCallback } from 'react';
import {
  View, Text, ScrollView, StyleSheet, SafeAreaView,
  TouchableOpacity, RefreshControl,
} from 'react-native';
import { getLatestReport, getIncidents, ScanReport, Incident } from '../core/apiClient';

const MITRE_TECHNIQUES: Record<string, { name: string; tactic: string }> = {
  'T1046': { name: 'Network Service Discovery', tactic: 'Reconnaissance' },
  'T1595': { name: 'Active Scanning', tactic: 'Reconnaissance' },
  'T1071': { name: 'Application Layer Protocol', tactic: 'Command and Control' },
  'T1573': { name: 'Encrypted Channel', tactic: 'Command and Control' },
  'T1041': { name: 'Exfiltration Over C2', tactic: 'Exfiltration' },
  'T1567': { name: 'Exfiltration Over Web Service', tactic: 'Exfiltration' },
  'T1059': { name: 'Command and Scripting', tactic: 'Execution' },
  'T1622': { name: 'Debugger Evasion', tactic: 'Defense Evasion' },
  'T1027': { name: 'Obfuscated Files', tactic: 'Defense Evasion' },
  'T1556': { name: 'Modify Auth Process', tactic: 'Credential Access' },
  'T1110': { name: 'Brute Force', tactic: 'Credential Access' },
  'T1550': { name: 'Alternate Auth Material', tactic: 'Lateral Movement' },
  'T1486': { name: 'Data Encrypted for Impact', tactic: 'Impact' },
  'T1499': { name: 'Endpoint DoS', tactic: 'Impact' },
  'T1566': { name: 'Phishing', tactic: 'Initial Access' },
  'T1552': { name: 'Unsecured Credentials', tactic: 'Credential Access' },
  'T1583': { name: 'Acquire Infrastructure', tactic: 'Resource Development' },
  'T1485': { name: 'Data Destruction', tactic: 'Impact' },
  'T1565': { name: 'Stored Data Manipulation', tactic: 'Impact' },
  'T1021': { name: 'Remote Services', tactic: 'Lateral Movement' },
  'T1048': { name: 'Exfil Over Alt Protocol', tactic: 'Exfiltration' },
};

const KILL_CHAIN_PHASES = [
  'RECONNAISSANCE', 'WEAPONIZATION', 'DELIVERY', 'EXPLOITATION',
  'INSTALLATION', 'C2', 'ACTIONS_ON_OBJECTIVES',
];

export default function XDRScreen() {
  const [report, setReport] = useState<ScanReport | null>(null);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(false);
  const [view, setView] = useState<'overview' | 'mitre' | 'killchain' | 'surface'>('overview');

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [r, incs] = await Promise.all([getLatestReport(), getIncidents()]);
      setReport(r);
      setIncidents(incs);
    } catch (e) {
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => { fetchData(); }, [fetchData]);

  // Collect all MITRE techniques from incidents
  const allMitre = new Set<string>();
  incidents.forEach(inc => inc.mitre_techniques?.forEach(m => allMitre.add(m)));
  report?.findings.forEach(f => {
    const map: Record<string, string[]> = {
      sourcesealcorp: ['T1556', 'T1110', 'T1566'],
      pinning: ['T1573', 'T1041'],
      keyhandling: ['T1556', 'T1552'],
      payments: ['T1485', 'T1565'],
      recovery_page: ['T1566', 'T1027'],
      multiplatform: ['T1622', 'T1027'],
    };
    (map[f.scenario] || []).forEach(m => allMitre.add(m));
  });

  // Kill chain coverage
  const killChainCoverage = new Set<string>();
  incidents.forEach(inc => inc.kill_chain_phases?.forEach(p => killChainCoverage.add(p)));

  return (
    <SafeAreaView style={styles.container}>
      {/* View switcher */}
      <View style={styles.viewBar}>
        {(['overview', 'mitre', 'killchain', 'surface'] as const).map(v => (
          <TouchableOpacity
            key={v}
            style={[styles.viewBtn, view === v && styles.viewBtnActive]}
            onPress={() => setView(v)}
          >
            <Text style={[styles.viewBtnText, view === v && styles.viewBtnTextActive]}>
              {v === 'overview' ? 'Vista general' : v === 'mitre' ? 'MITRE ATT&CK' : v === 'killchain' ? 'Kill Chain' : 'Attack Surface'}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <ScrollView
        refreshControl={<RefreshControl refreshing={loading} onRefresh={fetchData} tintColor="#2563eb" />}
        contentContainerStyle={styles.content}
      >
        {view === 'overview' && (
          <>
            <Text style={styles.sectionTitle}>📊 Estado del XDR</Text>
            <View style={styles.statGrid}>
              <View style={styles.statCard}>
                <Text style={[styles.statNum, { color: '#ef4444' }]}>{incidents.filter(i => i.severity === 'critical').length}</Text>
                <Text style={styles.statLabel}>CRÍTICOS</Text>
              </View>
              <View style={styles.statCard}>
                <Text style={[styles.statNum, { color: '#f97316' }]}>{incidents.filter(i => i.severity === 'high').length}</Text>
                <Text style={styles.statLabel}>ALTOS</Text>
              </View>
              <View style={styles.statCard}>
                <Text style={[styles.statNum, { color: '#2563eb' }]}>{allMitre.size}</Text>
                <Text style={styles.statLabel}>TÉCNICAS MITRE</Text>
              </View>
              <View style={styles.statCard}>
                <Text style={[styles.statNum, { color: '#f59e0b' }]}>{killChainCoverage.size}/{KILL_CHAIN_PHASES.length}</Text>
                <Text style={styles.statLabel}>FASES KC</Text>
              </View>
            </View>

            <Text style={styles.sectionTitle}>🛡 Sensores activos</Text>
            {[
              { name: 'RASP', desc: 'Runtime App Self-Protection', status: 'active' },
              { name: 'NDR', desc: 'Network Detection & Response', status: 'active' },
              { name: 'Deception Mesh', desc: 'Malla de engaño y canary tokens', status: 'active' },
              { name: 'ZTNA Gateway', desc: 'Zero Trust Network Access', status: 'monitoring' },
              { name: 'Honeypot', desc: 'C2 Sinkhole y endpoints trampa', status: 'active' },
            ].map(s => (
              <View key={s.name} style={styles.sensorCard}>
                <View style={styles.sensorHeader}>
                  <Text style={styles.sensorName}>{s.name}</Text>
                  <View style={[styles.sensorDot, s.status === 'active' ? styles.dotActive : styles.dotMonitor]} />
                </View>
                <Text style={styles.sensorDesc}>{s.desc}</Text>
                <Text style={styles.sensorStatus}>{s.status === 'active' ? '● Activo' : '◐ Monitoreo'}</Text>
              </View>
            ))}

            <Text style={styles.sectionTitle}>📡 Incidentes recientes ({incidents.length})</Text>
            {incidents.slice(0, 5).map(inc => (
              <View key={inc.id} style={[styles.incidentCard, { borderLeftColor: sevColor(inc.severity) }]}>
                <Text style={[styles.incSev, { color: sevColor(inc.severity) }]}>{inc.severity.toUpperCase()}</Text>
                <Text style={styles.incTitle}>{inc.title}</Text>
                <Text style={styles.incMeta}>Confianza: {inc.confidence}% · {inc.status}</Text>
              </View>
            ))}
          </>
        )}

        {view === 'mitre' && (
          <>
            <Text style={styles.sectionTitle}>🎯 Matriz MITRE ATT&CK v15</Text>
            <Text style={styles.subText}>Técnicas detectadas en el último scan</Text>
            
            {/* Group by tactic */}
            {Object.entries(
              Array.from(allMitre).reduce((acc, tech) => {
                const info = MITRE_TECHNIQUES[tech];
                if (info) {
                  if (!acc[info.tactic]) acc[info.tactic] = [];
                  acc[info.tactic].push({ tech, ...info });
                }
                return acc;
              }, {} as Record<string, any[]>)
            ).map(([tactic, techs]) => (
              <View key={tactic} style={styles.tacticCard}>
                <Text style={styles.tacticName}>{tactic}</Text>
                {techs.map(t => (
                  <View key={t.tech} style={styles.techRow}>
                    <Text style={styles.techId}>{t.tech}</Text>
                    <Text style={styles.techName}>{t.name}</Text>
                  </View>
                ))}
              </View>
            ))}
          </>
        )}

        {view === 'killchain' && (
          <>
            <Text style={styles.sectionTitle}>⛓ Cyber Kill Chain (Lockheed Martin)</Text>
            <Text style={styles.subText}>Progreso de intrusión detectado</Text>
            
            {KILL_CHAIN_PHASES.map((phase, i) => {
              const active = killChainCoverage.has(phase);
              const relatedIncidents = incidents.filter(inc => inc.kill_chain_phases?.includes(phase));
              return (
                <View key={phase} style={[styles.kcPhase, active && styles.kcPhaseActive]}>
                  <View style={styles.kcHeader}>
                    <Text style={[styles.kcNum, active ? styles.kcNumActive : null]}>{i + 1}</Text>
                    <Text style={[styles.kcName, active ? styles.kcNameActive : null]}>{phase}</Text>
                    {active && <Text style={styles.kcBadge}>⚠ DETECTADO</Text>}
                  </View>
                  {active && relatedIncidents.length > 0 && (
                    <Text style={styles.kcIncidents}>
                      {relatedIncidents.map(inc => inc.title.substring(0, 50)).join(', ')}
                    </Text>
                  )}
                  {i < KILL_CHAIN_PHASES.length - 1 && <Text style={styles.kcArrow}>↓</Text>}
                </View>
              );
            })}
          </>
        )}

        {view === 'surface' && (
          <>
            <Text style={styles.sectionTitle}>🗺 Attack Surface Map</Text>
            
            <Text style={styles.subText}>Endpoints expuestos</Text>
            {['POST /api/auth/login', 'POST /api/auth/recover', 'GET /api/hash/list', 'POST /api/payment/webhook', 'GET /api/health'].map(ep => (
              <View key={ep} style={styles.surfaceRow}>
                <Text style={styles.surfaceEndpoint}>{ep}</Text>
                <Text style={styles.surfaceRisk}>⚠</Text>
              </View>
            ))}

            <Text style={styles.subText}>Tecnologías detectadas</Text>
            {['Android APK', 'iOS IPA', 'API Gateway', 'WAF', 'ZTNA Gateway', 'Auth0/AuthProvider'].map(tech => (
              <View key={tech} style={styles.surfaceRow}>
                <Text style={styles.surfaceTech}>{tech}</Text>
              </View>
            ))}

            <Text style={styles.subText}>Vulnerabilidades conocidas</Text>
            {report?.findings.filter(f => f.severity === 'critical' || f.severity === 'high').slice(0, 8).map((f, i) => (
              <View key={i} style={[styles.vulnCard, { borderLeftColor: sevColor(f.severity) }]}>
                <Text style={[styles.vulnSev, { color: sevColor(f.severity) }]}>{f.severity.toUpperCase()}</Text>
                <Text style={styles.vulnTitle}>{f.title}</Text>
                <Text style={styles.vulnScenario}>Módulo: {f.scenario}</Text>
              </View>
            ))}
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function sevColor(sev: string): string {
  const map: Record<string, string> = {
    critical: '#ef4444', high: '#f97316', medium: '#f59e0b',
  };
  return map[sev] || '#8b949e';
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0d1117' },
  viewBar: { flexDirection: 'row', backgroundColor: '#161b22', borderBottomWidth: 1, borderBottomColor: '#30363d', paddingHorizontal: 4 },
  viewBtn: { flex: 1, paddingVertical: 10, alignItems: 'center' },
  viewBtnActive: { borderBottomWidth: 2, borderBottomColor: '#2563eb' },
  viewBtnText: { color: '#8b949e', fontSize: 11, fontWeight: '500' },
  viewBtnTextActive: { color: '#2563eb' },
  content: { padding: 16 },
  sectionTitle: { fontSize: 18, fontWeight: '600', color: '#c9d1d9', marginTop: 12, marginBottom: 8 },
  subText: { color: '#8b949e', fontSize: 13, marginBottom: 8 },
  statGrid: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between' },
  statCard: { backgroundColor: '#161b22', borderRadius: 12, padding: 12, width: '48%', marginBottom: 8, alignItems: 'center' },
  statNum: { fontSize: 28, fontWeight: 'bold' },
  statLabel: { fontSize: 10, color: '#8b949e', marginTop: 2 },
  sensorCard: { backgroundColor: '#161b22', borderRadius: 10, padding: 12, marginBottom: 6 },
  sensorHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  sensorName: { color: '#c9d1d9', fontSize: 15, fontWeight: '600' },
  sensorDesc: { color: '#8b949e', fontSize: 12, marginTop: 2 },
  sensorStatus: { fontSize: 12, marginTop: 4 },
  sensorDot: { width: 8, height: 8, borderRadius: 4 },
  dotActive: { backgroundColor: '#22c55e' },
  dotMonitor: { backgroundColor: '#f59e0b' },
  incidentCard: { backgroundColor: '#161b22', borderRadius: 8, padding: 10, marginBottom: 6, borderLeftWidth: 3 },
  incSev: { fontSize: 11, fontWeight: '700' },
  incTitle: { color: '#c9d1d9', fontSize: 13, marginTop: 2 },
  incMeta: { color: '#484f58', fontSize: 11, marginTop: 2 },
  // MITRE
  tacticCard: { backgroundColor: '#161b22', borderRadius: 10, padding: 12, marginBottom: 10 },
  tacticName: { color: '#2563eb', fontSize: 14, fontWeight: '600', marginBottom: 6 },
  techRow: { flexDirection: 'row', paddingVertical: 4, borderBottomWidth: 1, borderBottomColor: '#21262d' },
  techId: { color: '#f97316', fontSize: 12, fontFamily: 'monospace', width: 80 },
  techName: { color: '#c9d1d9', fontSize: 12, flex: 1 },
  // Kill chain
  kcPhase: { backgroundColor: '#161b22', borderRadius: 10, padding: 12, marginBottom: 4 },
  kcPhaseActive: { backgroundColor: '#ef444422', borderWidth: 1, borderColor: '#ef4444' },
  kcHeader: { flexDirection: 'row', alignItems: 'center' },
  kcNum: { color: '#484f58', fontSize: 18, fontWeight: 'bold', width: 30 },
  kcNumActive: { color: '#ef4444' },
  kcName: { color: '#484f58', fontSize: 14, flex: 1 },
  kcNameActive: { color: '#ef4444', fontWeight: '600' },
  kcBadge: { fontSize: 10, color: '#ef4444', fontWeight: '700' },
  kcIncidents: { color: '#8b949e', fontSize: 11, marginTop: 4, marginLeft: 30 },
  kcArrow: { color: '#30363d', fontSize: 16, textAlign: 'center', marginTop: 2 },
  // Attack surface
  surfaceRow: { flexDirection: 'row', justifyContent: 'space-between', backgroundColor: '#161b22', borderRadius: 8, padding: 10, marginBottom: 4 },
  surfaceEndpoint: { color: '#c9d1d9', fontSize: 13, fontFamily: 'monospace' },
  surfaceRisk: { color: '#f97316', fontSize: 14 },
  surfaceTech: { color: '#c9d1d9', fontSize: 13 },
  vulnCard: { backgroundColor: '#161b22', borderRadius: 8, padding: 10, marginBottom: 6, borderLeftWidth: 3 },
  vulnSev: { fontSize: 11, fontWeight: '700' },
  vulnTitle: { color: '#c9d1d9', fontSize: 13, marginTop: 2 },
  vulnScenario: { color: '#8b949e', fontSize: 11, marginTop: 2 },
});
