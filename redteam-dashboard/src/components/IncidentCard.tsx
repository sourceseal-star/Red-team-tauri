import React from 'react';
import { StyleSheet, View } from 'react-native';
import { Card, Text, Button, useTheme } from 'react-native-paper';
import { AppTheme } from '../theme/darkTheme';

interface IncidentCardProps {
  playbookName: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  timestamp: string;
  onExecute?: () => void;
}

export const IncidentCard: React.FC<IncidentCardProps> = ({
  playbookName,
  status,
  timestamp,
  onExecute,
}) => {
  const theme = useTheme<AppTheme>();

  const getStatusColor = () => {
    switch (status) {
      case 'completed':
        return theme.colors.success;
      case 'running':
        return theme.colors.primary;
      case 'pending':
        return theme.colors.warning;
      case 'failed':
        return theme.colors.danger;
      default:
        return theme.colors.muted;
    }
  };

  return (
    <Card style={[styles.card, { backgroundColor: theme.colors.surface, borderColor: theme.colors.surface === '#161b22' ? '#30363d' : '#21262d' }]}>
      <Card.Content>
        <View style={styles.header}>
          <Text variant="titleMedium" style={[styles.playbookName, { color: theme.colors.text }]}>
            {playbookName}
          </Text>
          <View style={[styles.statusBadge, { backgroundColor: getStatusColor() + '22', borderColor: getStatusColor() }]}>
            <Text style={[styles.statusText, { color: getStatusColor() }]}>
              {status.toUpperCase()}
            </Text>
          </View>
        </View>
        <Text variant="labelSmall" style={[styles.timestamp, { color: theme.colors.muted }]}>
          Triggered: {timestamp}
        </Text>
        <View style={styles.actions}>
          <Button
            mode="contained"
            onPress={onExecute}
            disabled={status === 'running'}
            buttonColor={theme.colors.primary}
            textColor="#ffffff"
            style={styles.button}
            labelStyle={styles.buttonLabel}
          >
            {status === 'running' ? 'Running Playbook...' : 'Execute Playbook'}
          </Button>
        </View>
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
    alignItems: 'flex-start',
    marginBottom: 6,
  },
  playbookName: {
    fontWeight: 'bold',
    flex: 1,
    marginRight: 8,
  },
  statusBadge: {
    borderWidth: 1,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 4,
  },
  statusText: {
    fontSize: 10,
    fontWeight: 'bold',
  },
  timestamp: {
    marginBottom: 12,
  },
  actions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
  },
  button: {
    borderRadius: 6,
  },
  buttonLabel: {
    fontSize: 12,
    fontWeight: 'bold',
  },
});
