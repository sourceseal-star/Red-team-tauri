import React, { useState, useCallback } from 'react';
import {
  View, Text, FlatList, TouchableOpacity, StyleSheet,
  ActivityIndicator, SafeAreaView, Modal, ScrollView,
} from 'react-native';
import { triggerScan, getLatestReport, getScanHistory, getModuleList, ScanReport } from '../core/apiClient';

export default function ScansScreen() {
  const [report, setReport] = useState<ScanReport | null>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState<string>('');
  const [selectedModule, setSelectedModule] = useState<any>(null);
  const [showModuleModal, setShowModuleModal] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [r, h] = await Promise.all([getLatestReport(), getScanHistory()]);
      setReport(r);
      setHistory(h);
    } catch (e) {
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => { fetchData(); }, [fetchData]);

  const handleNewScan = async () => {
    setScanning(true);
    setScanResult('');
    try {
      const result = await triggerScan();
      setScanResult(`✅ Scan completado · ${result.findings} hallazgos · ${result.elapsed}s`);
      await fetchData();
    } catch (e: any) {
      setScanResult(`❌ ${e.message}`);
    } finally {
      setScanning(false);
    }
  };

  const modules = getModuleList();
  const findingsByModule = (moduleName: string) => {
    return report?.findings.filter(f => f.scenario === moduleName) || [];
  };

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.content}>
        {/* Scan button */}
        <TouchableOpacity
          style={[styles.scanButton, scanning && styles.scanButtonDisabled]}
          onPress={handleNewScan}
          disabled={scanning}
          activeOpacity={0.8}
        >
          {scanning ? (
            <View style={styles.row}>
              <ActivityIndicator color="#fff" size="small" />
              <Text style={styles.scanButtonText}>Ejecutando scan...</Text>
            </View>
          ) : (
            <Text style={styles.scanButtonText}>▶ Ejecutar nuevo scan</Text>
          )}
        </TouchableOpacity>

        {scanResult ? <Text style={styles.scanResult}>{scanResult}</Text> : null}

        {/* Current report summary */}
        {report && (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>Reporte actual</Text>
            <View style={styles.row}>
              <Text style={styles.metric}>{report.total_findings}</Text>
              <Text style={styles.metricLabel}>hallazgos totales</Text>
            </View>
            <View style={styles.sevBar}>
              <Text style={{ color: '#ef4444' }}>🔴 {report.by_severity.critical}</Text>
              <Text style={{ color: '#f97316' }}>🟠 {report.by_severity.high}</Text>
              <Text style={{ color: '#f59e0b' }}>🟡 {report.by_severity.medium}</Text>
              <Text style={{ color: '#3b82f6' }}>🔵 {report.by_severity.low}</Text>
              <Text style={{ color: '#8b949e' }}>⚪ {report.by_severity.info}</Text>
            </View>
          </View>
        )}

        {/* Modules with findings */}
        <Text style={styles.sectionTitle}>Módulos y hallazgos</Text>
        {modules.map(mod => {
          const findings = findingsByModule(mod.name);
          const hasFail = findings.some(f => f.severity === 'high' || f.severity === 'critical');
          return (
            <TouchableOpacity
              key={mod.name}
              style={styles.moduleItem}
              onPress={() => { setSelectedModule({ ...mod, findings }); setShowModuleModal(true); }}
            >
              <View style={styles.moduleHeader}>
                <Text style={styles.moduleName}>{mod.name}</Text>
                <Text style={[styles.moduleBadge, hasFail ? styles.badgeFail : findings.length > 0 ? styles.badgePass : styles.badgeSkip]}>
                  {hasFail ? 'FAIL' : findings.length > 0 ? 'PASS' : 'SKIP'}
                </Text>
              </View>
              <Text style={styles.moduleDesc}>{mod.description}</Text>
              <Text style={styles.moduleFindings}>{findings.length} hallazgos</Text>
            </TouchableOpacity>
          );
        })}

        {/* History */}
        <Text style={styles.sectionTitle}>Historial de scans</Text>
        {history.map((h, i) => (
          <View key={i} style={styles.historyItem}>
            <Text style={styles.historyDate}>
              {new Date(h.finished_at).toLocaleDateString()} {new Date(h.finished_at).toLocaleTimeString()}
            </Text>
            <Text style={styles.historyFindings}>{h.total_findings} hallazgos</Text>
            <View style={styles.historySev}>
              {Object.entries(h.by_severity || {}).map(([sev, count]) => (
                <Text key={sev} style={{ color: sevColor(sev), fontSize: 12 }}>{sev}: {count as number}  </Text>
              ))}
            </View>
          </View>
        ))}
      </ScrollView>

      {/* Module detail modal */}
      <Modal visible={showModuleModal} animationType="slide" transparent={false}>
        <SafeAreaView style={styles.modalContainer}>
          <View style={styles.modalHeader}>
            <Text style={styles.modalTitle}>{selectedModule?.name}</Text>
            <TouchableOpacity onPress={() => setShowModuleModal(false)}>
              <Text style={styles.closeBtn}>✕</Text>
            </TouchableOpacity>
          </View>
          <ScrollView contentContainerStyle={{ padding: 16 }}>
            <Text style={styles.modalDesc}>{selectedModule?.description}</Text>
            <Text style={styles.sectionTitle}>Hallazgos ({selectedModule?.findings?.length || 0})</Text>
            {selectedModule?.findings?.map((f: any, i: number) => (
              <View key={i} style={[styles.findingCard, { borderLeftColor: sevColor(f.severity) }]}>
                <View style={styles.findingHeader}>
                  <Text style={[styles.findingSev, { color: sevColor(f.severity) }]}>
                    {f.severity.toUpperCase()}
                  </Text>
                  <Text style={styles.findingStatus}>{f.status}</Text>
                </View>
                <Text style={styles.findingTitle}>{f.title}</Text>
                <Text style={styles.findingDesc}>{f.description}</Text>
                <Text style={styles.findingRemediation}>🔧 {f.remediation}</Text>
              </View>
            ))}
            {(!selectedModule?.findings || selectedModule.findings.length === 0) && (
              <Text style={styles.empty}>Sin hallazgos para este módulo</Text>
            )}
          </ScrollView>
        </SafeAreaView>
      </Modal>
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
  scanButton: { backgroundColor: '#2563eb', paddingVertical: 16, borderRadius: 12, alignItems: 'center', marginBottom: 12 },
  scanButtonDisabled: { opacity: 0.6 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  scanButtonText: { color: '#fff', fontSize: 16, fontWeight: '600' },
  scanResult: { color: '#22c55e', fontSize: 14, textAlign: 'center', marginBottom: 12 },
  card: { backgroundColor: '#161b22', borderRadius: 12, padding: 16, marginBottom: 16 },
  cardTitle: { fontSize: 16, fontWeight: '600', color: '#c9d1d9', marginBottom: 8 },
  metric: { fontSize: 32, fontWeight: 'bold', color: '#c9d1d9' },
  metricLabel: { fontSize: 14, color: '#8b949e', marginLeft: 8, alignSelf: 'flex-end', paddingBottom: 4 },
  sevBar: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 12 },
  sectionTitle: { fontSize: 18, fontWeight: '600', color: '#c9d1d9', marginTop: 16, marginBottom: 8 },
  moduleItem: { backgroundColor: '#161b22', borderRadius: 12, padding: 14, marginBottom: 8 },
  moduleHeader: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 4 },
  moduleName: { color: '#c9d1d9', fontSize: 15, fontWeight: '600' },
  moduleDesc: { color: '#8b949e', fontSize: 13, marginTop: 2 },
  moduleFindings: { color: '#484f58', fontSize: 12, marginTop: 4 },
  moduleBadge: { fontSize: 11, fontWeight: '700', paddingHorizontal: 8, paddingVertical: 2, borderRadius: 4 },
  badgeFail: { backgroundColor: '#ef444422', color: '#ef4444' },
  badgePass: { backgroundColor: '#22c55e22', color: '#22c55e' },
  badgeSkip: { backgroundColor: '#8b949e22', color: '#8b949e' },
  historyItem: { backgroundColor: '#161b22', borderRadius: 8, padding: 12, marginBottom: 6 },
  historyDate: { color: '#c9d1d9', fontSize: 13 },
  historyFindings: { color: '#8b949e', fontSize: 13, marginTop: 2 },
  historySev: { flexDirection: 'row', marginTop: 4, flexWrap: 'wrap' },
  empty: { color: '#8b949e', textAlign: 'center', marginTop: 20 },
  // Modal
  modalContainer: { flex: 1, backgroundColor: '#0d1117' },
  modalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: 16, borderBottomWidth: 1, borderBottomColor: '#30363d' },
  modalTitle: { fontSize: 20, fontWeight: 'bold', color: '#c9d1d9' },
  closeBtn: { color: '#8b949e', fontSize: 20 },
  modalDesc: { color: '#8b949e', fontSize: 14, marginBottom: 8 },
  findingCard: { backgroundColor: '#161b22', borderRadius: 8, padding: 12, marginBottom: 8, borderLeftWidth: 3 },
  findingHeader: { flexDirection: 'row', justifyContent: 'space-between' },
  findingSev: { fontSize: 12, fontWeight: '700' },
  findingStatus: { color: '#484f58', fontSize: 11 },
  findingTitle: { color: '#c9d1d9', fontSize: 14, fontWeight: '500', marginTop: 4 },
  findingDesc: { color: '#8b949e', fontSize: 12, marginTop: 4 },
  findingRemediation: { color: '#3b82f6', fontSize: 12, marginTop: 4 },
});
