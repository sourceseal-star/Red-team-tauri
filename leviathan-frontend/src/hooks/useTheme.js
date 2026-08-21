import { useState, useEffect } from 'react';

/**
 * Hook personalizado para manejar el tema de la aplicación
 * @returns {Object} Objeto con el tema actual y función para cambiarlo
 */
export const useTheme = () => {
  const [theme, setTheme] = useState(() => {
    // Obtener tema desde localStorage o usar el tema por defecto
    return localStorage.getItem('theme') || 'leviathan';
  });

  // Aplicar tema al cuerpo del documento
  useEffect(() => {
    document.body.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  /**
   * Cambiar el tema
   * @param {string} newTheme - Nuevo tema a aplicar
   */
  const changeTheme = (newTheme) => {
    setTheme(newTheme);
  };

  /**
   * Alternar entre temas
   */
  const toggleTheme = () => {
    const themes = ['leviathan', 'light', 'dark'];
    const currentIndex = themes.indexOf(theme);
    const nextIndex = (currentIndex + 1) % themes.length;
    setTheme(themes[nextIndex]);
  };

  return {
    theme,
    changeTheme,
    toggleTheme,
    isDark: theme === 'leviathan' || theme === 'dark'
  };
};

/**
 * Componente para proveer el contexto de tema
 */
export const ThemeProvider = ({ children }) => {
  const themeState = useTheme();
  return children(themeState);
};

export default useTheme;
