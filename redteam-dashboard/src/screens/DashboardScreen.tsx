import React, { useState, useCallback } from 'react';
import {
  View, Text, ScrollView, RefreshControl, StyleSheet, SafeAreaView,
  TouchableOpacity,
} from 'react-native';
import ModuleCard from '../components/ModuleCard';
import AlertCard from '../components/AlertCard';
import { getLatestReport, ScanReport } from '../core/apiClient';

export default function DashboardScreen() {
  const [report, setReport] = useState<ScanReport | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getLatestReport();
      setReport(data);
    } catch (e) {
      setReport(null);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => { fetchData(); }, [fetchData]);

  const sevCount = report?.by_severity || { critical: 0, high: 0, medium: 0, low: 0, info: 0 };
  const alerts = report?.findings.filter(f => f.severity === 'critical' || f.severity === 'high') || [];
  
  const moduleList: Record<string, string> = {
    rng: 'Generador aleatorio', pinning: 'Certificate pinning', sidechannel: 'Canal lateral',
    keyhandling: 'KeyStore/Keychain', payments: 'Pagos y webhooks', biometric: 'Biometría',
    business_logic: 'Lógica de negocio', imei: 'Validación IMEI', multiplatform: 'Multiplataforma',
    sourcesealcorp: 'Controles A1-A10', recovery_page: 'Página de recuperación', pegasus: 'Spyware Pegasus',
  };

  const moduleStatuses = Object.keys(moduleList).map(name => {
    const results = report?.findings.filter(f => f.scenario === name) || [];
    const hasFail = results.some(r => r.severity === 'high' || r.severity === 'critical');
    const allSkipped = results.length > 0 && results.every(r => r.status === 'skipped');
    const status = allSkipped ? 'skipped' : hasFail ? 'fail' : results.length > 0 ? 'pass' : 'skipped';
    return { name, status, findings: results.length, description: moduleList[name] };
  });

  const passCount = moduleStatuses.filter(m => m.status === 'pass').length;
  const failCount = moduleStatuses.filter(m => m.status === 'fail').length;

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView
        refreshControl={<RefreshControl refreshing={loading} onRefresh={fetchData} tintColor="#2563eb" />}
        contentContainerStyle={styles.content}
      >
        {/* Status banner */}
        <View style={styles.statusBanner}>
          <View style={styles.statusItem}>
            <Text style={[styles.statusNum, { color: '#22c55e' }]}>{passCount}</Text>
            <Text style={styles.statusLabel}>PASS</Text>
          </View>
          <View style={styles.statusDivider} />
          <View style={styles.statusItem}>
            <Text style={[styles.statusNum, { color: '#ef4444' }]}>{failCount}</Text>
            <Text style={styles.statusLabel}>FAIL</Text>
          </View>
          <View style={styles.statusDivider} />
          <View style={styles.statusItem}>
            <Text style={[styles.statusNum, { color: '#8b949e' }]}>{12 - passCount - failCount}</Text>
            <Text style={styles.statusLabel}>SKIP</Text>
          </View>
        </View>

        {/* Last scan info */}
        {report && (
          <View style={styles.scanInfo}>
            <Text style={styles.scanInfoText}>Último scan: {new Date(report.finished_at).toLocaleString()}</Text>
            <Text style={styles.scanInfoSub}>Duración: {report.elapsed_seconds}s · {report.total_findings} hallazgos</Text>
          </View>
        )}

        {/* Severity counts */}
        <Text style={styles.sectionTitle}>Hallazgos por severidad</Text>
        <View style={styles.severityRow}>
          {(['critical', 'high', 'medium', 'low', 'info'] as const).map(sev => (
            <View key={sev} style={styles.severityBadge}>
              <Text style={[styles.severityCount, { color: sevColor(sev) }]}>{sevCount[sev] || 0}</Text>
              <Text style={styles.severityLabel}>{sev.toUpperCase()}</Text>
            </View>
          ))}
        </View>

        {/* Modules grid */}
        <Text style={styles.sectionTitle}>Módulos de scan</Text>
        <View style={styles.modulesGrid}>
          {moduleStatuses.map(m => (
            <ModuleCard
              key={m.name}
              title={m.name}
              status={m.status as any}
              findings={m.findings}
              onPress={() => {}}
            />
          ))}
        </View>

        {/* Active alerts */}
        {alerts.length > 0 && (
          <>
            <Text style={styles.sectionTitle}>🚨 Alertas activas ({alerts.length})</Text>
            {alerts.map((a, i) => (
              <AlertCard
                key={i}
                severity={a.severity as any}
                title={a.title}
                description={a.description}
                timestamp={a.timestamp}
              />
            ))}
          </>
        )}

        {/* Quick stats */}
        <Text style={styles.sectionTitle}>Resumen ejecutivo</Text>
        <View style={styles.execSummary}>
          <View style={styles.summaryRow}>
            <Text style={styles.summaryLabel}>Escenarios ejecutados:</Text>
            <Text style={styles.summaryValue}>{report?.scenarios_run?.length || 0}</Text>
          </View>
          <View style={styles.summaryRow}>
            <Text style={styles.summaryLabel}>Target analizado:</Text>
            <Text style={styles.summaryValue}>{report?.target || 'N/A'}</Text>
          </View>
          <View style={styles.summaryRow}>
            <Text style={styles.summaryLabel}>Backend:</Text>
            <Text style={styles.summaryValue}>{report?.backend ? 'Conectado' : 'Offline'}</Text>
          </View>
          <View style={styles.summaryRow}>
            <Text style={styles.summaryLabel}>Modo:</Text>
            <Text style={styles.summaryValue}>Local (offline-ready)</Text>
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

function sevColor(sev: string): string {
  const map: Record<string, string> = {
    critical: '#ef4444', high: '#f97316', medium: '#f59e0b',
    low: '#3b82f6', info: '#8b949e',
  };
  return map[sev] || '#8b949e';
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0d1117' },
  content: { padding: 16 },
  statusBanner: {
    flexDirection: 'row', justifyContent: 'center', alignItems: 'center',
    backgroundColor: '#161b22', borderRadius: 12, padding: 16, marginBottom: 12,
  },
  statusItem: { alignItems: 'center', flex: 1 },
  statusNum: { fontSize: 32, fontWeight: 'bold' },
  statusLabel: { fontSize: 12, color: '#8b949e', marginTop: 2 },
  statusDivider: { width: 1, height: 40, backgroundColor: '#30363d' },
  scanInfo: { backgroundColor: '#161b22', borderRadius: 8, padding: 12, marginBottom: 16 },
  scanInfoText: { color: '#c9d1d9', fontSize: 14 },
  scanInfoSub: { color: '#8b949e', fontSize: 12, marginTop: 4 },
  sectionTitle: { fontSize: 18, fontWeight: '600', color: '#c9d1d9', marginTop: 16, marginBottom: 8 },
  severityRow: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 16 },
  severityBadge: { alignItems: 'center', flex: 1 },
  severityCount: { fontSize: 24, fontWeight: 'bold' },
  severityLabel: { fontSize: 10, color: '#8b949e', marginTop: 2 },
  modulesGrid: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between' },
  execSummary: { backgroundColor: '#161b22', borderRadius: 12, padding: 16 },
  summaryRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 6 },
  summaryLabel: { color: '#8b949e', fontSize: 14 },
  summaryValue: { color: '#c9d1d9', fontSize: 14, fontWeight: '500' },
});
