import React, { useState, useCallback } from 'react';
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet,
  ActivityIndicator, SafeAreaView, Modal,
} from 'react-native';
import { getPlaybooks, triggerPlaybook, Playbook, getIncidents, Incident } from '../core/apiClient';

export default function SOARScreen() {
  const [playbooks, setPlaybooks] = useState<Playbook[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(false);
  const [executing, setExecuting] = useState<string | null>(null);
  const [execResult, setExecResult] = useState<string>('');
  const [selectedPlaybook, setSelectedPlaybook] = useState<Playbook | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [tab, setTab] = useState<'playbooks' | 'incidents'>('playbooks');

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [pbs, incs] = await Promise.all([getPlaybooks(), getIncidents()]);
      setPlaybooks(pbs);
      setIncidents(incs);
    } catch (e) {
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => { fetchData(); }, [fetchData]);

  const handleExecute = async (pb: Playbook) => {
    setExecuting(pb.name);
    setExecResult('');
    try {
      const result = await triggerPlaybook(pb.name);
      setExecResult(`✅ ${result.detail}`);
      setPlaybooks(prev => prev.map(p => p.name === pb.name ? { ...p, status: 'success' as any } : p));
    } catch (e: any) {
      setExecResult(`❌ ${e.message}`);
    } finally {
      setExecuting(null);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      {/* Tab switcher */}
      <View style={styles.tabBar}>
        <TouchableOpacity
          style={[styles.tab, tab === 'playbooks' && styles.tabActive]}
          onPress={() => setTab('playbooks')}
        >
          <Text style={[styles.tabText, tab === 'playbooks' && styles.tabTextActive]}>Playbooks ({playbooks.length})</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.tab, tab === 'incidents' && styles.tabActive]}
          onPress={() => setTab('incidents')}
        >
          <Text style={[styles.tabText, tab === 'incidents' && styles.tabTextActive]}>Incidentes ({incidents.length})</Text>
        </TouchableOpacity>
      </View>

      {execResult ? <Text style={styles.execResult}>{execResult}</Text> : null}

      <ScrollView contentContainerStyle={styles.content}>
        {tab === 'playbooks' ? (
          <>
            <Text style={styles.sectionTitle}>Playbooks de respuesta automática</Text>
            {loading ? (
              <ActivityIndicator color="#2563eb" style={{ marginTop: 20 }} />
            ) : (
              playbooks.map(pb => (
                <View key={pb.name} style={styles.playbookCard}>
                  <View style={styles.pbHeader}>
                    <Text style={styles.pbName}>{pb.name.replace(/_/g, ' ')}</Text>
                    <Text style={[styles.pbSeverity, { color: sevColorPB(pb.severity) }]}>
                      {pb.severity}
                    </Text>
                  </View>
                  <Text style={styles.pbDesc}>{pb.description}</Text>
                  
                  {/* MITRE techniques */}
                  <View style={styles.tagRow}>
                    {pb.mitre_techniques?.map(m => (
                      <View key={m} style={styles.mitreTag}>
                        <Text style={styles.mitreText}>{m}</Text>
                      </View>
                    ))}
                  </View>

                  {/* Steps preview */}
                  <Text style={styles.stepsLabel}>Pasos: {pb.steps?.length || 0}</Text>
                  <Text style={styles.stepsPreview}>
                    {(pb.steps || []).slice(0, 3).map((s, i) => `${i + 1}. ${s.name}`).join('\n')}
                    {(pb.steps?.length || 0) > 3 ? '\n...' : ''}
                  </Text>

                  {/* Status badge */}
                  {pb.status !== 'idle' && (
                    <Text style={[styles.pbStatus, pb.status === 'success' ? styles.pbStatusOk : styles.pbStatusFail]}>
                      {pb.status === 'success' ? '✅ Ejecutado' : '❌ Falló'}
                    </Text>
                  )}

                  <View style={styles.pbActions}>
                    <TouchableOpacity
                      style={styles.detailBtn}
                      onPress={() => { setSelectedPlaybook(pb); setShowModal(true); }}
                    >
                      <Text style={styles.detailBtnText}>Ver detalles</Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                      style={[styles.executeBtn, executing === pb.name && styles.executeBtnDisabled]}
                      onPress={() => handleExecute(pb)}
                      disabled={executing === pb.name}
                    >
                      {executing === pb.name ? (
                        <ActivityIndicator color="#fff" size="small" />
                      ) : (
                        <Text style={styles.executeBtnText}>▶ Ejecutar</Text>
                      )}
                    </TouchableOpacity>
                  </View>
                </View>
              ))
            )}
          </>
        ) : (
          <>
            <Text style={styles.sectionTitle}>Incidentes activos</Text>
            {incidents.map(inc => (
              <View key={inc.id} style={[styles.incidentCard, { borderLeftColor: sevColorPB(inc.severity.toUpperCase()) }]}>
                <View style={styles.incHeader}>
                  <Text style={[styles.incSev, { color: sevColorPB(inc.severity.toUpperCase()) }]}>
                    {inc.severity.toUpperCase()}
                  </Text>
                  <Text style={styles.incStatus}>{inc.status}</Text>
                </View>
                <Text style={styles.incTitle}>{inc.title}</Text>
                <Text style={styles.incDesc}>{inc.description}</Text>
                
                <View style={styles.incMeta}>
                  <Text style={styles.incConfidence}>Confianza: {inc.confidence}%</Text>
                  <Text style={styles.incTime}>{new Date(inc.timestamp).toLocaleString()}</Text>
                </View>

                {/* MITRE */}
                <View style={styles.tagRow}>
                  {inc.mitre_techniques?.map(m => (
                    <View key={m} style={styles.mitreTag}>
                      <Text style={styles.mitreText}>{m}</Text>
                    </View>
                  ))}
                </View>

                {/* Kill chain */}
                <View style={styles.killChainRow}>
                  {inc.kill_chain_phases?.map((phase, i) => (
                    <Text key={i} style={styles.killChainPhase}>
                      {i > 0 ? ' → ' : ''}{phase}
                    </Text>
                  ))}
                </View>
              </View>
            ))}
          </>
        )}
      </ScrollView>

      {/* Playbook detail modal */}
      <Modal visible={showModal} animationType="slide" transparent={false}>
        <SafeAreaView style={styles.modalContainer}>
          <View style={styles.modalHeader}>
            <Text style={styles.modalTitle}>{selectedPlaybook?.name.replace(/_/g, ' ')}</Text>
            <TouchableOpacity onPress={() => setShowModal(false)}>
              <Text style={styles.closeBtn}>✕</Text>
            </TouchableOpacity>
          </View>
          <ScrollView contentContainerStyle={{ padding: 16 }}>
            <Text style={styles.modalDesc}>{selectedPlaybook?.description}</Text>
            
            <Text style={styles.sectionTitle}>Secuencia de pasos (DAG)</Text>
            {selectedPlaybook?.steps?.map((step, i) => (
              <View key={step.id} style={styles.stepCard}>
                <View style={styles.stepHeader}>
                  <Text style={styles.stepNum}>Paso {i + 1}</Text>
                  <Text style={styles.stepHandler}>{step.handler}</Text>
                </View>
                <Text style={styles.stepName}>{step.name}</Text>
                <Text style={styles.stepDetail}>Timeout: {step.timeout_seconds}s</Text>
                <Text style={styles.stepDetail}>Depende de: {step.depends_on?.length ? step.depends_on.join(', ') : 'inicio'}</Text>
                {step.rollback_handler ? (
                  <Text style={styles.stepRollback}>↩ Rollback: {step.rollback_handler}</Text>
                ) : null}
                {step.mitre_technique ? (
                  <Text style={styles.stepMitre}>MITRE: {step.mitre_technique}</Text>
                ) : null}
                {step.params && Object.keys(step.params).length > 0 ? (
                  <View style={styles.stepParams}>
                    {Object.entries(step.params).map(([k, v]) => (
                      <Text key={k} style={styles.stepParam}>
                        {k}: {String(v).substring(0, 50)}
                      </Text>
                    ))}
                  </View>
                ) : null}
              </View>
            ))}

            {/* Execute from modal */}
            <TouchableOpacity
              style={styles.executeBtn}
              onPress={() => selectedPlaybook && handleExecute(selectedPlaybook)}
              disabled={executing === selectedPlaybook?.name}
            >
              {executing === selectedPlaybook?.name ? (
                <ActivityIndicator color="#fff" />
              ) : (
                <Text style={styles.executeBtnText}>▶ Ejecutar playbook</Text>
              )}
            </TouchableOpacity>
            {execResult ? <Text style={styles.execResult}>{execResult}</Text> : null}
          </ScrollView>
        </SafeAreaView>
      </Modal>
    </SafeAreaView>
  );
}

function sevColorPB(sev: string): string {
  const map: Record<string, string> = {
    CRITICAL: '#ef4444', HIGH: '#f97316', MEDIUM: '#f59e0b', LOW: '#3b82f6',
  };
  return map[sev] || '#8b949e';
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0d1117' },
  tabBar: { flexDirection: 'row', backgroundColor: '#161b22', borderBottomWidth: 1, borderBottomColor: '#30363d' },
  tab: { flex: 1, paddingVertical: 14, alignItems: 'center' },
  tabActive: { borderBottomWidth: 2, borderBottomColor: '#2563eb' },
  tabText: { color: '#8b949e', fontSize: 14, fontWeight: '500' },
  tabTextActive: { color: '#2563eb' },
  content: { padding: 16 },
  sectionTitle: { fontSize: 18, fontWeight: '600', color: '#c9d1d9', marginBottom: 8 },
  execResult: { color: '#22c55e', fontSize: 13, textAlign: 'center', paddingVertical: 8 },
  // Playbook cards
  playbookCard: { backgroundColor: '#161b22', borderRadius: 12, padding: 14, marginBottom: 12 },
  pbHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  pbName: { color: '#c9d1d9', fontSize: 16, fontWeight: '600', flex: 1, textTransform: 'capitalize' },
  pbSeverity: { fontSize: 12, fontWeight: '700' },
  pbDesc: { color: '#8b949e', fontSize: 13, marginTop: 6 },
  tagRow: { flexDirection: 'row', flexWrap: 'wrap', marginTop: 8 },
  mitreTag: { backgroundColor: '#2563eb22', borderRadius: 4, paddingHorizontal: 6, paddingVertical: 2, marginRight: 4, marginBottom: 4 },
  mitreText: { color: '#2563eb', fontSize: 11 },
  stepsLabel: { color: '#484f58', fontSize: 12, marginTop: 6 },
  stepsPreview: { color: '#8b949e', fontSize: 12, marginTop: 4 },
  pbStatus: { fontSize: 12, marginTop: 6 },
  pbStatusOk: { color: '#22c55e' },
  pbStatusFail: { color: '#ef4444' },
  pbActions: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 10 },
  detailBtn: { backgroundColor: '#30363d', borderRadius: 8, paddingVertical: 8, paddingHorizontal: 16 },
  detailBtnText: { color: '#c9d1d9', fontSize: 13 },
  executeBtn: { backgroundColor: '#2563eb', borderRadius: 8, paddingVertical: 8, paddingHorizontal: 16, alignItems: 'center' },
  executeBtnDisabled: { opacity: 0.5 },
  executeBtnText: { color: '#fff', fontSize: 13, fontWeight: '600' },
  // Incident cards
  incidentCard: { backgroundColor: '#161b22', borderRadius: 12, padding: 14, marginBottom: 10, borderLeftWidth: 3 },
  incHeader: { flexDirection: 'row', justifyContent: 'space-between' },
  incSev: { fontSize: 12, fontWeight: '700' },
  incStatus: { color: '#8b949e', fontSize: 11, textTransform: 'capitalize' },
  incTitle: { color: '#c9d1d9', fontSize: 15, fontWeight: '500', marginTop: 4 },
  incDesc: { color: '#8b949e', fontSize: 12, marginTop: 4 },
  incMeta: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 8 },
  incConfidence: { color: '#f59e0b', fontSize: 12 },
  incTime: { color: '#484f58', fontSize: 11 },
  killChainRow: { flexDirection: 'row', flexWrap: 'wrap', marginTop: 6 },
  killChainPhase: { color: '#2563eb', fontSize: 11 },
  // Modal
  modalContainer: { flex: 1, backgroundColor: '#0d1117' },
  modalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: 16, borderBottomWidth: 1, borderBottomColor: '#30363d' },
  modalTitle: { fontSize: 20, fontWeight: 'bold', color: '#c9d1d9', textTransform: 'capitalize' },
  closeBtn: { color: '#8b949e', fontSize: 20 },
  modalDesc: { color: '#8b949e', fontSize: 14, marginBottom: 12 },
  stepCard: { backgroundColor: '#161b22', borderRadius: 8, padding: 12, marginBottom: 8 },
  stepHeader: { flexDirection: 'row', justifyContent: 'space-between' },
  stepNum: { color: '#2563eb', fontSize: 13, fontWeight: '600' },
  stepHandler: { color: '#f97316', fontSize: 12, fontFamily: 'monospace' },
  stepName: { color: '#c9d1d9', fontSize: 14, fontWeight: '500', marginTop: 4 },
  stepDetail: { color: '#8b949e', fontSize: 12, marginTop: 2 },
  stepRollback: { color: '#ef4444', fontSize: 11, marginTop: 2 },
  stepMitre: { color: '#2563eb', fontSize: 11, marginTop: 2 },
  stepParams: { backgroundColor: '#0d1117', borderRadius: 6, padding: 8, marginTop: 6 },
  stepParam: { color: '#8b949e', fontSize: 11, fontFamily: 'monospace' },
});
