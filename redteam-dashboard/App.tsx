import React from 'react';
import { Provider as PaperProvider } from 'react-native-paper';
import { AuthProvider } from './src/context/AuthContext';
import { AppNavigator } from './src/navigation/AppNavigator';
import { darkTheme } from './src/theme/darkTheme';

export default function App() {
  return (
    <AuthProvider>
      <PaperProvider theme={darkTheme}>
        <AppNavigator />
      </PaperProvider>
    </AuthProvider>
  );
}
