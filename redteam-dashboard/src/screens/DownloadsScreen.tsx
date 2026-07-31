import React, { useState, useCallback } from 'react';
import {
  View, Text, FlatList, TouchableOpacity, StyleSheet,
  SafeAreaView, Linking, Alert,
} from 'react-native';
import { getDownloads, DownloadItem } from '../core/apiClient';

export default function DownloadsScreen() {
  const [items, setItems] = useState<DownloadItem[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getDownloads();
      setItems(data);
    } catch (e) {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => { fetchData(); }, [fetchData]);

  const handleDownload = (item: DownloadItem) => {
    if (item.url) {
      Linking.openURL(item.url);
    } else {
      Alert.alert(
        'Descargar',
        `${item.name} (${item.size})\n\nEn modo offline, los archivos están disponibles en el servidor Red-team. Conecta al backend para descargas directas.`,
        [{ text: 'OK' }]
      );
    }
  };

  const typeIcon = (type: string) => {
    switch (type) {
      case 'report': return '📄';
      case 'evidence': return '🔍';
      case 'apk': return '📦';
      case 'strings': return '🔤';
      default: return '📁';
    }
  };

  const typeLabel = (type: string) => {
    switch (type) {
      case 'report': return 'Reporte';
      case 'evidence': return 'Evidencia';
      case 'apk': return 'APK';
      case 'strings': return 'Strings';
      default: return type;
    }
  };

  // Group by type
  const grouped = items.reduce((acc, item) => {
    if (!acc[item.type]) acc[item.type] = [];
    acc[item.type].push(item);
    return acc;
  }, {} as Record<string, DownloadItem[]>);

  const typeOrder = ['report', 'evidence', 'apk', 'strings'];

  return (
    <SafeAreaView style={styles.container}>
      <Text style={styles.title}>Archivos y descargas</Text>
      <Text style={styles.subtitle}>Reportes, evidencia, APKs y análisis de strings</Text>

      <FlatList
        data={typeOrder.filter(t => grouped[t]?.length)}
        keyExtractor={t => t}
        refreshing={loading}
        onRefresh={fetchData}
        renderItem={({ item: type }) => (
          <View style={styles.group}>
            <Text style={styles.groupTitle}>
              {typeIcon(type)} {typeLabel(type)} ({grouped[type].length})
            </Text>
            {grouped[type].map((item, i) => (
              <TouchableOpacity
                key={item.id || i}
                style={styles.fileItem}
                onPress={() => handleDownload(item)}
              >
                <View style={styles.fileInfo}>
                  <Text style={styles.fileName}>{item.name}</Text>
                  <Text style={styles.fileMeta}>
                    {item.size} · {new Date(item.date).toLocaleDateString()}
                  </Text>
                </View>
                <Text style={styles.downloadIcon}>⬇</Text>
              </TouchableOpacity>
            ))}
          </View>
        )}
        ListEmptyComponent={
          loading
            ? <Text style={styles.empty}>Cargando archivos...</Text>
            : <Text style={styles.empty}>No hay archivos disponibles.</Text>
        }
        contentContainerStyle={styles.list}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0d1117' },
  title: { fontSize: 24, fontWeight: 'bold', color: '#c9d1d9', paddingHorizontal: 16, paddingTop: 16 },
  subtitle: { fontSize: 13, color: '#8b949e', paddingHorizontal: 16, marginBottom: 8 },
  list: { padding: 16 },
  group: { marginBottom: 16 },
  groupTitle: { fontSize: 16, fontWeight: '600', color: '#c9d1d9', marginBottom: 8 },
  fileItem: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    backgroundColor: '#161b22', borderRadius: 10, padding: 12, marginBottom: 6,
  },
  fileInfo: { flex: 1 },
  fileName: { color: '#c9d1d9', fontSize: 14, fontFamily: 'monospace' },
  fileMeta: { color: '#8b949e', fontSize: 12, marginTop: 2 },
  downloadIcon: { color: '#2563eb', fontSize: 20 },
  empty: { color: '#8b949e', textAlign: 'center', marginTop: 32 },
});
