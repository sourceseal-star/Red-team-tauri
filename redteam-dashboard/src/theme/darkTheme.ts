import { MD3DarkTheme, MD3Theme } from 'react-native-paper';

export interface ThemeColors {
  primary: string;
  background: string;
  surface: string;
  text: string;
  danger: string;
  success: string;
  warning: string;
  muted: string;
}

export interface AppTheme extends Omit<MD3Theme, 'colors'> {
  colors: MD3Theme['colors'] & ThemeColors;
}

export const darkTheme: AppTheme = {
  ...MD3DarkTheme,
  colors: {
    ...MD3DarkTheme.colors,
    primary: '#2563eb',
    background: '#0d1117',
    surface: '#161b22',
    text: '#c9d1d9',
    danger: '#ef4444',
    success: '#22c55e',
    warning: '#f59e0b',
    muted: '#8b949e',
    // Map standard MD3 colors to keep React Native Paper components aligned
    onSurface: '#c9d1d9',
    outline: '#8b949e',
    surfaceVariant: '#161b22',
    onSurfaceVariant: '#c9d1d9',
  },
};
