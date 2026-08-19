#!/usr/bin/env python3
"""
Deploy ARTO - Script de Despliegue
===================================
Script para desplegar el sistema ARTO en tu proyecto Red-Team-Tauri.

Uso:
    python3 deploy_arto.py [--install] [--start] [--test]

Opciones:
    --install   Instala dependencias necesarias
    --start     Inicia el sistema ARTO
    --test      Ejecuta pruebas de integración
    --help      Muestra esta ayuda

Ejemplo:
    python3 deploy_arto.py --install --start
"""

import os
import sys
import subprocess
import argparse
import asyncio
from pathlib import Path
from typing import List, Optional


class DeployARTO:
    """Clase para desplegar ARTO"""
    
    def __init__(self):
        self.base_dir = Path(__file__).parent.parent
        self.arto_dir = self.base_dir / "arto"
        self.frontend_dir = self.base_dir / "frontend"
        self.scripts_dir = self.base_dir / "scripts"
        
        # Verificar si estamos en el directorio correcto
        if not self._is_redteam_tauri_project():
            print("⚠️  ADVERTENCIA: No parece ser un proyecto Red-Team-Tauri")
            print("    Asegúrate de ejecutar este script desde la raíz de tu proyecto")
    
    def _is_redteam_tauri_project(self) -> bool:
        """Verifica si estamos en un proyecto Red-Team-Tauri"""
        # Verificar archivos clave
        required_files = [
            "backend",
            "frontend",
            "redteam"
        ]
        
        for file in required_files:
            if not (self.base_dir / file).exists():
                return False
        
        return True
    
    def check_dependencies(self) -> List[str]:
        """Verifica dependencias de Python"""
        required_packages = [
            "fastapi",
            "uvicorn",
            "aiohttp",
            "sqlite3",
            "python-multipart"
        ]
        
        missing = []
        
        for package in required_packages:
            try:
                __import__(package)
            except ImportError:
                missing.append(package)
        
        return missing
    
    def install_dependencies(self) -> bool:
        """Instala dependencias de Python"""
        print("📦 Instalando dependencias de Python...")
        
        try:
            # Instalar con pip
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "fastapi", "uvicorn", "aiohttp", "python-multipart"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            print("✅ Dependencias de Python instaladas")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Error al instalar dependencias: {e}")
            return False
    
    def check_frontend_dependencies(self) -> List[str]:
        """Verifica dependencias del frontend"""
        required_packages = [
            "react",
            "typescript",
            "vite",
            "@types/react"
        ]
        
        missing = []
        
        # Verificar package.json
        package_json = self.frontend_dir / "package.json"
        if not package_json.exists():
            return required_packages
        
        # En implementación completa, verificar si los paquetes están en package.json
        return missing
    
    def install_frontend_dependencies(self) -> bool:
        """Instala dependencias del frontend"""
        print("📦 Instalando dependencias del frontend...")
        
        try:
            # Cambiar a directorio frontend
            os.chdir(self.frontend_dir)
            
            # Instalar con npm
            subprocess.run(
                ["npm", "install"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            print("✅ Dependencias del frontend instaladas")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Error al instalar dependencias del frontend: {e}")
            return False
        finally:
            os.chdir(self.base_dir)
    
    def create_structure(self) -> bool:
        """Crea la estructura de directorios de ARTO"""
        print("📁 Creando estructura de directorios...")
        
        try:
            # Crear directorios principales
            directories = [
                "arto",
                "arto/core",
                "arto/modules",
                "arto/memory",
                "arto/utils",
                "arto/api",
                "arto/models",
                "frontend/src/components",
                "frontend/src/components/types",
                "frontend/src/api",
                "scripts"
            ]
            
            for dir_path in directories:
                (self.base_dir / dir_path).mkdir(parents=True, exist_ok=True)
            
            # Crear archivos __init__.py
            init_files = [
                "arto",
                "arto/core",
                "arto/modules",
                "arto/memory",
                "arto/utils",
                "arto/api",
                "arto/models",
                "frontend/src/components/types"
            ]
            
            for init_path in init_files:
                init_file = self.base_dir / init_path / "__init__.py"
                if not init_file.exists():
                    with open(init_file, 'w') as f:
                        f.write("# ARTO - Automated Red Team Operations\n")
            
            print("✅ Estructura de directorios creada")
            return True
        except Exception as e:
            print(f"❌ Error al crear estructura: {e}")
            return False
    
    def copy_files(self) -> bool:
        """Copia los archivos de ARTO (simulación - en realidad ya están en el canvas)"""
        print("📝 Copiando archivos de ARTO...")
        
        # En una implementación real, esto copiaría desde una fuente
        # Por ahora, solo mostramos el mensaje
        print("✅ Archivos de ARTO listos para ser copiados")
        print("   NOTA: Copia manualmente el contenido de cada sección del canvas")
        print("   a su archivo correspondiente")
        return True
    
    async def test_integration(self) -> bool:
        """Prueba la integración con ARTO"""
        print("🧪 Probando integración con ARTO...")
        
        try:
            # Probar importación
            sys.path.insert(0, str(self.base_dir))
            
            # Intentar importar ARTO
            try:
                from arto import arto
                print("✅ Módulo ARTO importado correctamente")
            except ImportError as e:
                print(f"⚠️  No se pudo importar ARTO: {e}")
                print("   Asegúrate de haber copiado todos los archivos")
                return False
            
            # Probar inicialización
            try:
                await arto.start()
                print("✅ ARTO inicializado correctamente")
                
                # Probar operación simple
                result = await arto.autonomous_operation("example.com", "scan")
                print("✅ Operación de prueba ejecutada")
                
                await arto.stop()
                print("✅ ARTO detenido correctamente")
                
                return True
            except Exception as e:
                print(f"❌ Error al probar ARTO: {e}")
                return False
                
        except Exception as e:
            print(f"❌ Error en pruebas de integración: {e}")
            return False
    
    def integrate_with_backend(self) -> bool:
        """Integra ARTO con el backend existente"""
        print("🔧 Integrando ARTO con el backend...")
        
        try:
            # Buscar main.py o app.py
            backend_files = ["main.py", "app.py"]
            backend_dir = self.base_dir / "backend"
            
            for file in backend_files:
                backend_file = backend_dir / file
                if backend_file.exists():
                    print(f"📄 Encontrado {file}")
                    
                    # Leer contenido
                    with open(backend_file, 'r') as f:
                        content = f.read()
                    
                    # Verificar si ya está integrado
                    if "from arto.api.arto_router import router as arto_router" in content:
                        print(f"✅ ARTO ya está integrado en {file}")
                        return True
                    
                    # Agregar importación
                    if "from fastapi import FastAPI" in content:
                        print(f"📝 Agregando importación de ARTO a {file}")
                        
                        # Buscar la línea de FastAPI
                        lines = content.split('\n')
                        for i, line in enumerate(lines):
                            if "from fastapi import FastAPI" in line:
                                # Agregar importación después
                                lines.insert(i + 1, "from arto.api.arto_router import router as arto_router")
                                break
                        
                        content = '\n'.join(lines)
                        
                        # Agregar router
                        if "app = FastAPI()" in content:
                            lines = content.split('\n')
                            for i, line in enumerate(lines):
                                if "app = FastAPI()" in line:
                                    # Agregar router después
                                    lines.insert(i + 1, "app.include_router(arto_router)")
                                    break
                            
                            content = '\n'.join(lines)
                        
                        # Guardar cambios
                        with open(backend_file, 'w') as f:
                            f.write(content)
                        
                        print(f"✅ ARTO integrado en {file}")
                        return True
            
            print("⚠️  No se encontró main.py o app.py en backend/")
            return False
            
        except Exception as e:
            print(f"❌ Error al integrar con backend: {e}")
            return False
    
    def integrate_with_frontend(self) -> bool:
        """Integra ARTO con el frontend existente"""
        print("🎨 Integrando ARTO con el frontend...")
        
        try:
            frontend_src = self.frontend_dir / "src"
            
            # Buscar App.tsx o main.tsx
            frontend_files = ["App.tsx", "App.tsx", "main.tsx"]
            
            for file in frontend_files:
                frontend_file = frontend_src / file
                if frontend_file.exists():
                    print(f"📄 Encontrado {file}")
                    
                    # Leer contenido
                    with open(frontend_file, 'r') as f:
                        content = f.read()
                    
                    # Verificar si ya está integrado
                    if "ARTOProvider" in content:
                        print(f"✅ ARTO ya está integrado en {file}")
                        return True
                    
                    # Agregar importación
                    if "import React" in content:
                        print(f"📝 Agregando importación de ARTOProvider a {file}")
                        
                        # Buscar la línea de React
                        lines = content.split('\n')
                        for i, line in enumerate(lines):
                            if "import React" in line:
                                # Agregar importación después
                                lines.insert(i + 1, "import { ARTOProvider } from './components/ARTOProvider';")
                                break
                        
                        content = '\n'.join(lines)
                        
                        # Agregar ARTOProvider
                        if "function App()" in content:
                            lines = content.split('\n')
                            for i, line in enumerate(lines):
                                if "function App()" in line:
                                    # Buscar el return
                                    for j in range(i, min(i + 20, len(lines))):
                                        if "return (" in lines[j]:
                                            # Agregar ARTOProvider antes del return
                                            lines.insert(j, 
                                                "  // ARTO Provider\n" + 
                                                "  <ARTOProvider autoConnect autoStart>"
                                            )
                                            # Agregar cierre después del return
                                            for k in range(j + 1, len(lines)):
                                                if ")" in lines[k] and "return" not in lines[k]:
                                                    lines.insert(k, "  </ARTOProvider>")
                                                    break
                                            break
                                    break
                            
                            content = '\n'.join(lines)
                        
                        # Guardar cambios
                        with open(frontend_file, 'w') as f:
                            f.write(content)
                        
                        print(f"✅ ARTO integrado en {file}")
                        return True
            
            print("⚠️  No se encontró App.tsx o main.tsx en frontend/src/")
            return False
            
        except Exception as e:
            print(f"❌ Error al integrar con frontend: {e}")
            return False
    
    async def run(self, install: bool = False, start: bool = False, test: bool = False) -> bool:
        """Ejecuta el despliegue"""
        print("\n" + "="*60)
        print("🚀 DESPLIEGUE DE ARTO - SISTEMA DE OPERACIONES AUTÓNOMAS")
        print("="*60 + "\n")
        
        all_success = True
        
        # Paso 1: Verificar estructura
        if not self._is_redteam_tauri_project():
            print("⚠️  No estás en un proyecto Red-Team-Tauri")
            print("    Continúa de todos modos? (s/n): ", end="")
            response = input().lower()
            if response != 's':
                return False
        
        # Paso 2: Crear estructura
        if not self.create_structure():
            all_success = False
        
        # Paso 3: Instalar dependencias
        if install:
            missing_py = self.check_dependencies()
            if missing_py:
                print(f"⚠️  Dependencias de Python faltantes: {', '.join(missing_py)}")
                if not self.install_dependencies():
                    all_success = False
            
            missing_frontend = self.check_frontend_dependencies()
            if missing_frontend:
                print(f"⚠️  Dependencias del frontend faltantes")
                if not self.install_frontend_dependencies():
                    all_success = False
        
        # Paso 4: Copiar archivos
        if not self.copy_files():
            all_success = False
        
        # Paso 5: Integrar con backend
        if not self.integrate_with_backend():
            all_success = False
        
        # Paso 6: Integrar con frontend
        if not self.integrate_with_frontend():
            all_success = False
        
        # Paso 7: Probar integración
        if test:
            if not await self.test_integration():
                all_success = False
        
        # Paso 8: Iniciar sistema
        if start:
            print("\n🚀 Iniciando sistema ARTO...")
            try:
                from arto import arto, start_arto
                await start_arto()
                print("✅ ARTO iniciado")
                print("\n📊 ARTO está listo para usar!")
                print("   - API disponible en: /api/arto/*")
                print("   - WebSocket disponible en: /api/arto/ws")
                print("   - Panel ARTO disponible en tu frontend")
            except Exception as e:
                print(f"❌ Error al iniciar ARTO: {e}")
                all_success = False
        
        # Resumen
        print("\n" + "="*60)
        if all_success:
            print("✅ DESPLIEGUE COMPLETADO CON ÉXITO")
        else:
            print("⚠️  DESPLIEGUE COMPLETADO CON ADVERTENCIAS")
        print("="*60 + "\n")
        
        return all_success


def main():
    """Función principal"""
    parser = argparse.ArgumentParser(
        description="Despliega el sistema ARTO en Red-Team-Tauri"
    )
    parser.add_argument(
        "--install",
        action="store_true",
        help="Instala dependencias necesarias"
    )
    parser.add_argument(
        "--start",
        action="store_true",
        help="Inicia el sistema ARTO después del despliegue"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Ejecuta pruebas de integración"
    )
    
    args = parser.parse_args()
    
    deployer = DeployARTO()
    
    # Ejecutar despliegue
    success = asyncio.run(deployer.run(
        install=args.install,
        start=args.start,
        test=args.test
    ))
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
