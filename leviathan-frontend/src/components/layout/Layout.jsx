import React, { useState, useEffect } from 'react';
import { Outlet } from 'react-router-dom';
import SidebarCompact from './SidebarCompact';
import Topbar from './Topbar';
import './layout.css';

const Layout = ({ children }) => {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [theme, setTheme] = useState(localStorage.getItem('theme') || 'leviathan');
  const [isMobile, setIsMobile] = useState(false);
  
  // Detectar si es móvil
  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth <= 768);
    };
    
    checkMobile();
    window.addEventListener('resize', checkMobile);
    
    return () => window.removeEventListener('resize', checkMobile);
  }, []);
  
  // Aplicar tema
  useEffect(() => {
    document.body.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);
  
  // Cerrar sidebar en móvil al navegar
  useEffect(() => {
    if (isMobile) {
      setSidebarOpen(false);
    }
  }, [isMobile]);
  
  const toggleSidebar = () => {
    setSidebarOpen(!sidebarOpen);
  };
  
  const toggleTheme = () => {
    const themes = ['leviathan', 'light', 'dark'];
    const currentIndex = themes.indexOf(theme);
    const nextIndex = (currentIndex + 1) % themes.length;
    setTheme(themes[nextIndex]);
  };
  
  return (
    <div className="app-layout">
      {/* Sidebar Compacto */}
      <SidebarCompact 
        isOpen={sidebarOpen} 
        onToggle={toggleSidebar}
        isMobile={isMobile}
      />
      
      {/* Contenido Principal */}
      <div className={`main-content ${sidebarOpen && !isMobile ? 'sidebar-open' : 'sidebar-closed'}`}>
        {/* Topbar */}
        <Topbar 
          onMenuClick={toggleSidebar} 
          onThemeClick={toggleTheme}
          currentTheme={theme}
        />
        
        {/* Contenido */}
        <main className="content">
          {children || <Outlet />}
        </main>
      </div>
      
      {/* Overlay para Mobile */}
      {sidebarOpen && isMobile && (
        <div className="sidebar-overlay" onClick={toggleSidebar} />
      )}
    </div>
  );
};

export default Layout;
