import React, { useState } from 'react';
import {
  View, Text, ScrollView, StyleSheet, SafeAreaView,
  TouchableOpacity, Switch, TextInput, Alert,
} from 'react-native';
import { useAuth } from '../context/AuthContext';
import { saveSecure, loadSecure, deleteSecure } from '../core/secureStorage';

export default function SettingsScreen() {
  const { logout } = useAuth();
  const [apiUrl, setApiUrl] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [scanTarget, setScanTarget] = useState('');
  const [autoScan, setAutoScan] = useState(false);
  const [biometricLock, setBiometricLock] = useState(true);
  const [notifications, setNotifications] = useState(true);
  const [darkMode] = useState(true);
  const [saved, setSaved] = useState(false);

  React.useEffect(() => {
    (async () => {
      const url = await loadSecure('api_url');
      const key = await loadSecure('api_key');
      const target = await loadSecure('scan_target');
      if (url) setApiUrl(url);
      if (key) setApiKey(key);
      if (target) setScanTarget(target);
    })();
  }, []);

  const handleSave = async () => {
    try {
      if (apiUrl) await saveSecure('api_url', apiUrl);
      if (apiKey) await saveSecure('api_key', apiKey);
      if (scanTarget) await saveSecure('scan_target', scanTarget);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      Alert.alert('Error', 'No se pudo guardar la configuración');
    }
  };

  const handleClearData = () => {
    Alert.alert(
      'Limpiar datos',
      '¿Eliminar toda la configuración guardada?',
      [
        { text: 'Cancelar', style: 'cancel' },
        {
          text: 'Eliminar',
          style: 'destructive',
          onPress: async () => {
            await deleteSecure('api_url');
            await deleteSecure('api_key');
            await deleteSecure('scan_target');
            setApiUrl('');
            setApiKey('');
            setScanTarget('');
            Alert.alert('✅', 'Datos eliminados');
          },
        },
      ]
    );
  };

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.content}>
        {/* Connection settings */}
        <Text style={styles.sectionTitle}>🔌 Conexión al backend</Text>
        <View style={styles.card}>
          <Text style={styles.label}>URL del API</Text>
          <TextInput
            style={styles.input}
            value={apiUrl}
            onChangeText={setApiUrl}
            placeholder="https://api.sourceseal.corp"
            placeholderTextColor="#484f58"
            autoCapitalize="none"
          />
          <Text style={styles.label}>API Key</Text>
          <TextInput
            style={styles.input}
            value={apiKey}
            onChangeText={setApiKey}
            placeholder="default_sourceseal_secret_key"
            placeholderTextColor="#484f58"
            secureTextEntry
          />
          <Text style={styles.label}>Target de scan (APK/IPA)</Text>
          <TextInput
            style={styles.input}
            value={scanTarget}
            onChangeText={setScanTarget}
            placeholder="/evidence/dummy.apk"
            placeholderTextColor="#484f58"
          />
        </View>

        {/* Scan settings */}
        <Text style={styles.sectionTitle}>⚙ Configuración de scans</Text>
        <View style={styles.card}>
          <View style={styles.toggleRow}>
            <Text style={styles.toggleLabel}>Auto-scan diario</Text>
            <Switch value={autoScan} onValueChange={setAutoScan} trackColor={{ true: '#2563eb' }} />
          </View>
          <View style={styles.toggleRow}>
            <Text style={styles.toggleLabel}>Notificaciones de alertas</Text>
            <Switch value={notifications} onValueChange={setNotifications} trackColor={{ true: '#2563eb' }} />
          </View>
          <View style={styles.toggleRow}>
            <Text style={styles.toggleLabel}>Bloqueo biométrico</Text>
            <Switch value={biometricLock} onValueChange={setBiometricLock} trackColor={{ true: '#2563eb' }} />
          </View>
        </View>

        {/* Module info */}
        <Text style={styles.sectionTitle}>📋 Módulos disponibles</Text>
        <View style={styles.card}>
          {[
            'RNG', 'Pinning', 'Side-channel', 'Key handling', 'Payments',
            'Biometric', 'Business logic', 'IMEI', 'Multiplatform',
            'SourceSealCorp A1-A10', 'Recovery page', 'Pegasus',
          ].map(m => (
            <View key={m} style={styles.moduleRow}>
              <Text style={styles.moduleName}>✅ {m}</Text>
            </View>
          ))}
        </View>

        {/* About */}
        <Text style={styles.sectionTitle}>ℹ Acerca de</Text>
        <View style={styles.card}>
          <Text style={styles.aboutText}>SourceSealCorp Red Team Dashboard</Text>
          <Text style={styles.aboutVersion}>v1.0.0 · Expo SDK 52</Text>
          <Text style={styles.aboutText}>Backend: Python orchestrator v2.1</Text>
          <Text style={styles.aboutText}>SOAR Engine v1.0 · XDR v15</Text>
          <Text style={styles.aboutText}>MITRE ATT&CK v15</Text>
          <Text style={styles.aboutText}>Modo: Offline-ready + Live API</Text>
        </View>

        {/* Actions */}
        <TouchableOpacity style={styles.saveBtn} onPress={handleSave}>
          <Text style={styles.saveBtnText}>{saved ? '✅ Guardado' : '💾 Guardar configuración'}</Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.clearBtn} onPress={handleClearData}>
          <Text style={styles.clearBtnText}>🗑 Limpiar datos</Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.logoutBtn} onPress={logout}>
          <Text style={styles.logoutBtnText}>🚪 Cerrar sesión</Text>
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0d1117' },
  content: { padding: 16 },
  sectionTitle: { fontSize: 18, fontWeight: '600', color: '#c9d1d9', marginTop: 12, marginBottom: 8 },
  card: { backgroundColor: '#161b22', borderRadius: 12, padding: 14, marginBottom: 8 },
  label: { color: '#8b949e', fontSize: 13, marginBottom: 4, marginTop: 8 },
  input: { backgroundColor: '#0d1117', borderRadius: 8, padding: 10, color: '#c9d1d9', fontSize: 14, borderWidth: 1, borderColor: '#30363d' },
  toggleRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 8 },
  toggleLabel: { color: '#c9d1d9', fontSize: 14 },
  moduleRow: { paddingVertical: 4 },
  moduleName: { color: '#c9d1d9', fontSize: 13 },
  aboutText: { color: '#c9d1d9', fontSize: 13, marginTop: 4 },
  aboutVersion: { color: '#8b949e', fontSize: 12, marginTop: 2 },
  saveBtn: { backgroundColor: '#2563eb', borderRadius: 10, padding: 14, alignItems: 'center', marginTop: 12 },
  saveBtnText: { color: '#fff', fontSize: 15, fontWeight: '600' },
  clearBtn: { backgroundColor: '#161b22', borderRadius: 10, padding: 14, alignItems: 'center', marginTop: 8, borderWidth: 1, borderColor: '#f59e0b' },
  clearBtnText: { color: '#f59e0b', fontSize: 14 },
  logoutBtn: { backgroundColor: '#161b22', borderRadius: 10, padding: 14, alignItems: 'center', marginTop: 8, marginBottom: 20, borderWidth: 1, borderColor: '#ef4444' },
  logoutBtnText: { color: '#ef4444', fontSize: 14, fontWeight: '600' },
});
