import React, { useState } from 'react';
import {
  View, StyleSheet, TouchableOpacity,
} from 'react-native';
import { Text, TextInput, Button, useTheme, ActivityIndicator } from 'react-native-paper';
import { useAuth } from '../context/AuthContext';
import { AppTheme } from '../theme/darkTheme';
import { checkBiometricAvailability, authenticateBiometric } from '../core/biometric';
import { apiClient } from '../core/apiClient';

export default function LoginScreen() {
  const { login } = useAuth();
  const theme = useTheme<AppTheme>();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [biometricSupported, setBiometricSupported] = useState(false);
  const [error, setError] = useState('');

  React.useEffect(() => {
    checkBiometricAvailability().then(setBiometricSupported);
  }, []);

  const handleLogin = async () => {
    if (!username || !password) {
      setError('Usuario y contraseña requeridos');
      return;
    }
    setLoading(true);
    setError('');
    try {
      // Autenticación real contra el backend — sin mock tokens
      const response = await apiClient.post<{ token: string; ok: boolean }>(
        '/api/auth/login',
        { username, password }
      );
      if (response.data?.ok && response.data?.token) {
        await login(response.data.token);
      } else {
        setError('Credenciales inválidas');
      }
    } catch (e: any) {
      const detail = e?.response?.data?.error || e?.message || 'Error de conexión al backend';
      setError(detail);
    } finally {
      setLoading(false);
    }
  };

  const handleBiometric = async () => {
    setLoading(true);
    setError('');
    try {
      const result = await authenticateBiometric();
      if (result.success) {
        // Biometría verifica identidad local; obtén token del backend igualmente
        const response = await apiClient.post<{ token: string; ok: boolean }>(
          '/api/auth/biometric',
          { verified: true }
        );
        if (response.data?.ok && response.data?.token) {
          await login(response.data.token);
        } else {
          setError('Backend rechazó la sesión biométrica');
        }
      } else {
        setError(result.message);
      }
    } catch (e: any) {
      setError(e?.response?.data?.error || e?.message || 'Error de autenticación biométrica');
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={[styles.container, { backgroundColor: '#0d1117' }]}>
      <View style={styles.logoContainer}>
        <Text style={styles.logo}>🔒</Text>
        <Text style={[styles.title, { color: '#c9d1d9' }]}>SourceSealCorp</Text>
        <Text style={[styles.subtitle, { color: '#8b949e' }]}>Red Team Dashboard</Text>
      </View>

      <View style={styles.formContainer}>
        <TextInput
          label="Usuario"
          value={username}
          onChangeText={setUsername}
          mode="outlined"
          style={styles.input}
          autoCapitalize="none"
          theme={{ colors: { primary: '#2563eb' } }}
        />
        <TextInput
          label="Contraseña"
          value={password}
          onChangeText={setPassword}
          secureTextEntry
          mode="outlined"
          style={styles.input}
          theme={{ colors: { primary: '#2563eb' } }}
        />

        {error ? <Text style={styles.errorText}>{error}</Text> : null}

        {loading ? (
          <ActivityIndicator style={styles.loader} color="#2563eb" size="large" />
        ) : (
          <Button
            mode="contained"
            onPress={handleLogin}
            style={styles.button}
            buttonColor="#2563eb"
            contentStyle={{ paddingVertical: 6 }}
          >
            Iniciar sesión
          </Button>
        )}

        {biometricSupported && (
          <TouchableOpacity onPress={handleBiometric} disabled={loading} style={styles.biometricBtn}>
            <Text style={styles.biometricText}>🔓 Autenticar con biometría</Text>
          </TouchableOpacity>
        )}
      </View>

      <View style={styles.footer}>
        <Text style={styles.footerText}>v1.0.0 · Expo Go · 12 módulos activos</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  logoContainer: { alignItems: 'center', marginBottom: 40 },
  logo: { fontSize: 48, marginBottom: 12 },
  title: { fontSize: 28, fontWeight: 'bold' },
  subtitle: { fontSize: 16, marginTop: 4 },
  formContainer: { width: '100%', maxWidth: 360 },
  input: { marginBottom: 12, backgroundColor: '#161b22' },
  button: { marginTop: 8, borderRadius: 8 },
  biometricBtn: { marginTop: 16, alignItems: 'center', padding: 12 },
  biometricText: { color: '#2563eb', fontSize: 15 },
  errorText: { color: '#ef4444', fontSize: 13, marginBottom: 8, textAlign: 'center' },
  loader: { marginTop: 16 },
  footer: { position: 'absolute', bottom: 20 },
  footerText: { color: '#484f58', fontSize: 12 },
});
