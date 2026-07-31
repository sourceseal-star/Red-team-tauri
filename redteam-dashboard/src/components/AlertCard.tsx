import React from 'react';
import { StyleSheet, View } from 'react-native';
import { Card, Text, useTheme } from 'react-native-paper';
import { AppTheme } from '../theme/darkTheme';

interface AlertCardProps {
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info';
  title: string;
  description: string;
  timestamp: string;
}

export const AlertCard: React.FC<AlertCardProps> = ({
  severity,
  title,
  description,
  timestamp,
}) => {
  const theme = useTheme<AppTheme>();

  const getSeverityColor = () => {
    switch (severity) {
      case 'critical':
        return theme.colors.danger;
      case 'high':
        return theme.colors.danger;
      case 'medium':
        return theme.colors.warning;
      case 'low':
        return theme.colors.primary;
      case 'info':
        return theme.colors.success;
      default:
        return theme.colors.muted;
    }
  };

  return (
    <Card style={[styles.card, { backgroundColor: theme.colors.surface, borderColor: theme.colors.surface === '#161b22' ? '#30363d' : '#21262d' }]}>
      <Card.Content>
        <View style={styles.header}>
          <View style={[styles.badge, { backgroundColor: getSeverityColor() + '22', borderColor: getSeverityColor() }]}>
            <Text style={[styles.badgeText, { color: getSeverityColor() }]}>
              {severity.toUpperCase()}
            </Text>
          </View>
          <Text variant="labelSmall" style={{ color: theme.colors.muted }}>
            {timestamp}
          </Text>
        </View>
        <Text variant="titleMedium" style={[styles.title, { color: theme.colors.text }]}>
          {title}
        </Text>
        <Text variant="bodyMedium" style={[styles.description, { color: theme.colors.muted }]}>
          {description}
        </Text>
      </Card.Content>
    </Card>
  );
};

const styles = StyleSheet.create({
  card: {
    marginVertical: 8,
    marginHorizontal: 16,
    borderRadius: 8,
    borderWidth: 1,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
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
  title: {
    fontWeight: 'bold',
    marginBottom: 6,
  },
  description: {
    lineHeight: 18,
  },
});
