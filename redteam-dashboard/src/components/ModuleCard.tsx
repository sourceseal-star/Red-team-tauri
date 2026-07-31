import React from 'react';
import { StyleSheet, View } from 'react-native';
import { Card, Text, useTheme } from 'react-native-paper';
import { AppTheme } from '../theme/darkTheme';

interface ModuleCardProps {
  title: string;
  status: 'pass' | 'fail' | 'skipped' | 'error';
  findingsCount: number;
  onPress?: () => void;
}

export const ModuleCard: React.FC<ModuleCardProps> = ({
  title,
  status,
  findingsCount,
  onPress,
}) => {
  const theme = useTheme<AppTheme>();

  const getBorderColor = () => {
    switch (status) {
      case 'pass':
        return theme.colors.success;
      case 'fail':
        return theme.colors.danger;
      case 'skipped':
        return theme.colors.muted;
      case 'error':
        return theme.colors.warning;
      default:
        return theme.colors.muted;
    }
  };

  const getStatusLabel = () => {
    return status.toUpperCase();
  };

  return (
    <Card
      style={[styles.card, { backgroundColor: theme.colors.surface, borderColor: getBorderColor() }]}
      onPress={onPress}
    >
      <Card.Content>
        <View style={styles.header}>
          <Text variant="titleMedium" style={[styles.title, { color: theme.colors.text }]}>
            {title}
          </Text>
          <View style={[styles.badge, { backgroundColor: getBorderColor() + '22', borderColor: getBorderColor() }]}>
            <Text style={[styles.badgeText, { color: getBorderColor() }]}>
              {getStatusLabel()}
            </Text>
          </View>
        </View>
        <View style={styles.footer}>
          <Text variant="bodyMedium" style={{ color: theme.colors.muted }}>
            Findings Detected:
          </Text>
          <Text variant="bodyLarge" style={{ color: findingsCount > 0 ? theme.colors.danger : theme.colors.success, fontWeight: 'bold' }}>
            {findingsCount}
          </Text>
        </View>
      </Card.Content>
    </Card>
  );
};

const styles = StyleSheet.create({
  card: {
    marginVertical: 8,
    marginHorizontal: 16,
    borderWidth: 1.5,
    borderRadius: 8,
    elevation: 2,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  title: {
    fontWeight: 'bold',
    flex: 1,
    marginRight: 8,
  },
  badge: {
    borderWidth: 1,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 4,
  },
  badgeText: {
    fontSize: 10,
    fontWeight: 'bold',
  },
  footer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 8,
  },
});
