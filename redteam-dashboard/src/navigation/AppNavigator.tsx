import React from 'react';
import { View, StyleSheet } from 'react-native';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Text, useTheme } from 'react-native-paper';
import { useAuth } from '../context/AuthContext';
import { AppTheme } from '../theme/darkTheme';
import DashboardScreen from '../screens/DashboardScreen';
import ScansScreen from '../screens/ScansScreen';
import SOARScreen from '../screens/SOARScreen';
import XDRScreen from '../screens/XDRScreen';
import DownloadsScreen from '../screens/DownloadsScreen';
import SettingsScreen from '../screens/SettingsScreen';
import LoginScreen from '../screens/LoginScreen';

const Tab = createBottomTabNavigator();

function MainTabs() {
  const theme = useTheme<AppTheme>();
  return (
    <Tab.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: '#0d1117' },
        headerTintColor: '#c9d1d9',
        tabBarStyle: { backgroundColor: '#161b22', borderTopColor: '#30363d' },
        tabBarActiveTintColor: '#2563eb',
        tabBarInactiveTintColor: '#8b949e',
      }}
    >
      <Tab.Screen
        name="Dashboard"
        component={DashboardScreen}
        options={{ tabBarLabel: 'Inicio', title: 'Red Team Dashboard' }}
      />
      <Tab.Screen
        name="Scans"
        component={ScansScreen}
        options={{ tabBarLabel: 'Scans', title: 'Escaneos' }}
      />
      <Tab.Screen
        name="SOAR"
        component={SOARScreen}
        options={{ tabBarLabel: 'SOAR', title: 'Respuesta Automática' }}
      />
      <Tab.Screen
        name="XDR"
        component={XDRScreen}
        options={{ tabBarLabel: 'XDR', title: 'Detección y Respuesta' }}
      />
      <Tab.Screen
        name="Downloads"
        component={DownloadsScreen}
        options={{ tabBarLabel: 'Archivos', title: 'Descargas' }}
      />
      <Tab.Screen
        name="Settings"
        component={SettingsScreen}
        options={{ tabBarLabel: 'Ajustes', title: 'Configuración' }}
      />
    </Tab.Navigator>
  );
}

export function AppNavigator() {
  const { isAuthenticated } = useAuth();

  if (!isAuthenticated) {
    return <LoginScreen />;
  }

  return (
    <NavigationContainer>
      <MainTabs />
    </NavigationContainer>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', alignItems: 'center' },
});
