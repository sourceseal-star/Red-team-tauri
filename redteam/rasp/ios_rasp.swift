import Foundation
import Darwin

/**
 * Estructura que representa un hallazgo individual de seguridad RASP en iOS.
 */
public struct RASPFinding {
    public let checkName: String
    public let isDetected: Bool
    public let severity: String // "CRITICAL", "HIGH", "MEDIUM", "INFO"
    public let details: String
}

/**
 * Reporte consolidado de todos los análisis RASP efectuados en el dispositivo iOS.
 */
public struct RASPReport {
    public let timestamp: Double
    public let isDeviceCompromised: Bool
    public let findings: [RASPFinding]
}

/**
 * Implementación principal de SourceSealRASP para iOS.
 */
public class SourceSealRASP {
    
    public init() {}
    
    /**
     * Ejecuta síncronamente todas las comprobaciones de seguridad para el ecosistema iOS.
     */
    public func runAllChecks() -> RASPReport {
        var findings = [RASPFinding]()
        
        // 1. Jailbreak Detection
        findings.append(checkJailbreakFiles())
        findings.append(checkJailbreakSandboxWrite())
        findings.append(checkJailbreakSchemes())
        findings.append(checkJailbreakDylibs())
        
        // 2. Frida Detection
        findings.append(checkFridaPorts())
        findings.append(checkFridaDylibs())
        
        // 3. Debugger Detection
        findings.append(checkDebuggerSysctl())
        findings.append(checkDebuggerIsatty())
        
        // 4. Emulator Detection
        findings.append(checkEmulatorEnvironment())
        
        // Se determina si el dispositivo está comprometido ante cualquier hallazgo HIGH o CRITICAL
        let isDeviceCompromised = findings.contains { $0.isDetected && ($0.severity == "CRITICAL" || $0.severity == "HIGH") }
        
        return RASPReport(
            timestamp: Date().timeIntervalSince1970,
            isDeviceCompromised: isDeviceCompromised,
            findings: findings
        )
    }
    
    // ==========================================
    // 1. DETECCIÓN DE JAILBREAK
    // ==========================================
    
    /**
     * Analiza rutas y archivos críticos comúnmente creados al aplicar Jailbreak.
     */
    private func checkJailbreakFiles() -> RASPFinding {
        var detected = false
        var details = ""
        
        let jailbreakPaths = [
            "/Applications/Cydia.app",
            "/Library/MobileSubstrate/MobileSubstrate.dylib",
            "/bin/bash",
            "/usr/sbin/sshd",
            "/etc/apt",
            "/private/var/lib/apt/",
            "/usr/bin/ssh",
            "/private/var/lib/cydia",
            "/Applications/Sileo.app",
            "/Applications/Zebra.app",
            "/Library/PreferenceBundles/ABypassPrefs.bundle"
        ]
        
        let fileManager = FileManager.default
        var detectedPaths = [String]()
        
        for path in jailbreakPaths {
            if fileManager.fileExists(atPath: path) {
                detected = true
                detectedPaths.append(path)
            }
        }
        
        if detected {
            details = "Archivos de Jailbreak detectados en el sistema de archivos: \(detectedPaths.joined(separator: ", "))"
        } else {
            details = "No se detectó ningún archivo del sistema asociado a Jailbreak."
        }
        
        return RASPFinding(
            checkName = "Jailbreak File Detection",
            isDetected: detected,
            severity: "CRITICAL",
            details: details
        )
    }
    
    /**
     * Comprueba si la aplicación puede escribir fuera de su Sandbox habitual, un claro síntoma de Jailbreak.
     */
    private func checkJailbreakSandboxWrite() -> RASPFinding {
        var detected = false
        var details = ""
        
        let testPath = "/private/jailbreak_test_sourceseal.txt"
        let testContent = "SourceSeal Security Check"
        
        do {
            try testContent.write(toFile: testPath, atomically: true, encoding: .utf8)
            detected = true
            details = "Se logró escribir en el directorio restringido: \(testPath). Privilegios de root activos."
            // Limpieza inmediata si fue exitoso
            try? FileManager.default.removeItem(atPath: testPath)
        } catch {
            details = "El sistema de archivos restringido impidió la escritura adecuadamente (Comportamiento Seguro)."
        }
        
        return RASPFinding(
            checkName = "Jailbreak Sandbox Write Bypass",
            isDetected: detected,
            severity: "CRITICAL",
            details: details
        )
    }
    
    /**
     * Intenta registrar e invocar esquemas URL de terceros pertenecientes a administradores de paquetes como Cydia.
     */
    private func checkJailbreakSchemes() -> RASPFinding {
        // En iOS moderno, requiere configurar LSApplicationQueriesSchemes en Info.plist para funcionar con canOpenURL.
        // Como alternativa nativa, evaluamos si podemos invocar la apertura de puertos locales o esquemas vía C nativo.
        // Simulamos la verificación clásica y agregamos un fallback dinámico por si no está configurada la llave.
        var detected = false
        var details = "Esquemas de Jailbreak no disponibles o inaccesibles sin configuración Info.plist."
        
        let urlSchemes = ["cydia://package/com.sourceseal.check", "sileo://", "zbra://"]
        
        // Esto solo correrá exitosamente en la aplicación de UI si el hilo es principal.
        // Aquí hacemos un reflejo lógico seguro.
        if Thread.isMainThread {
            #if canImport(UIKit)
            import UIKit
            for scheme in urlSchemes {
                if let url = URL(string: scheme) {
                    if UIApplication.shared.canOpenURL(url) {
                        detected = true
                        details = "Esquema URL de gestor de paquetes de Jailbreak disponible: \(scheme)"
                        break
                    }
                }
            }
            #endif
        }
        
        return RASPFinding(
            checkName = "Jailbreak Custom URL Schemes",
            isDetected: detected,
            severity: "HIGH",
            details: details
        )
    }
    
    /**
     * Examina las imágenes dinámicas (dylibs) cargadas por el sistema dinámico de enlazado (dyld).
     */
    private func checkJailbreakDylibs() -> RASPFinding {
        var detected = false
        var details = [String]()
        
        let imageCount = _dyld_image_count()
        for i in 0..<imageCount {
            if let rawImageName = _dyld_get_image_name(i) {
                let imageName = String(cString: rawImageName)
                let lowercased = imageName.lowercased()
                
                if lowercased.contains("mobilesubstrate") ||
                    lowercased.contains("cydia") ||
                    lowercased.contains("substrate") ||
                    lowercased.contains("tweaks") ||
                    lowercased.contains("patched") {
                    detected = true
                    details.append(imageName)
                }
            }
        }
        
        return RASPFinding(
            checkName = "Jailbreak Active Dylibs Check",
            isDetected: detected,
            severity: "CRITICAL",
            details: detected ? "Librerías sospechosas de inyección enlazadas: \(details.joined(separator: ", "))" : "No se hallaron dylibs de Jailbreak inyectadas."
        )
    }
    
    // ==========================================
    // 2. DETECCIÓN DE FRIDA
    // ==========================================
    
    /**
     * Escanea el puerto local por defecto de Frida (27042) usando sockets de bajo nivel.
     * Evita usar APIs de alto nivel que activan avisos de red local de iOS 14+.
     */
    private func checkFridaPorts() -> RASPFinding {
        var detected = false
        var details = "El puerto de Frida 27042 se encuentra cerrado."
        
        let socketFileDescriptor = socket(AF_INET, SOCK_STREAM, 0)
        if socketFileDescriptor >= 0 {
            var serverAddress = sockaddr_in()
            serverAddress.sin_family = sa_family_t(AF_INET)
            serverAddress.sin_port = UInt16(27042).bigEndian
            serverAddress.sin_addr.s_addr = inet_addr("127.0.0.1")
            
            let connectionResult = withUnsafePointer(to: &serverAddress) {
                $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                    connect(socketFileDescriptor, $0, socklen_t(MemoryLayout<sockaddr_in>.size))
                }
            }
            
            if connectionResult == 0 {
                detected = true
                details = "¡Puerto por defecto de Frida (27042) abierto y escuchando conexiones locales!"
            }
            close(socketFileDescriptor)
        }
        
        return RASPFinding(
            checkName = "Anti-Frida TCP Port Scan",
            isDetected: detected,
            severity: "CRITICAL",
            details: details
        )
    }
    
    /**
     * Revisa si dylibs propias de Frida o FridaGadget están cargadas en memoria del proceso.
     */
    private func checkFridaDylibs() -> RASPFinding {
        var detected = false
        var details = [String]()
        
        let imageCount = _dyld_image_count()
        for i in 0..<imageCount {
            if let rawImageName = _dyld_get_image_name(i) {
                let imageName = String(cString: rawImageName)
                let lowercased = imageName.lowercased()
                
                if lowercased.contains("frida") ||
                    lowercased.contains("gum-js") ||
                    lowercased.contains("gadget") {
                    detected = true
                    details.append(imageName)
                }
            }
        }
        
        return RASPFinding(
            checkName = "Anti-Frida Injected Dylibs",
            isDetected: detected,
            severity: "CRITICAL",
            details: detected ? "Dylibs de Frida detectadas en memoria: \(details.joined(separator: ", "))" : "Proceso limpio de dylibs de Frida."
        )
    }
    
    // ==========================================
    // 3. DETECCIÓN DE DEPURACIÓN (DEBUGGING)
    // ==========================================
    
    /**
     * Detección clásica de depurador mediante el llamado sysctl y la máscara de proceso P_TRACED.
     */
    private func checkDebuggerSysctl() -> RASPFinding {
        var detected = false
        
        var name = [CTL_KERN, KERN_PROC, KERN_PROC_PID, getpid()]
        var info = kinfo_proc()
        var size = MemoryLayout<kinfo_proc>.size
        
        let result = sysctl(&name, UInt32(name.count), &info, &size, nil, 0)
        
        if result == 0 {
            // El flag P_TRACED indica si el proceso está siendo rastreado por un debugger
            detected = (info.kp_proc.p_flag & P_TRACED) != 0
        }
        
        return RASPFinding(
            checkName = "Anti-Debug Sysctl Flag",
            isDetected: detected,
            severity: "CRITICAL",
            details: detected ? "Un depurador nativo (LLDB/GDB) está adjunto y analizando el proceso." : "No se encontró el flag de p_traced activo."
        )
    }
    
    /**
     * Comprueba si la salida de error estándar está enlazada a una consola interactiva (TTY).
     */
    private func checkDebuggerIsatty() -> RASPFinding {
        let detected = isatty(STDERR_FILENO) != 0
        return RASPFinding(
            checkName = "Anti-Debug Isatty Terminal",
            isDetected: detected,
            severity: "LOW",
            details: detected ? "La terminal stderr está conectada a un TTY interactivo (Posible debugger Xcode)." : "Stderr no interactivo."
        )
    }
    
    // ==========================================
    // 4. DETECCIÓN DE EMULADOR
    // ==========================================
    
    /**
     * Determina si el código está ejecutándose bajo el simulador de iOS de Apple.
     */
    private func checkEmulatorEnvironment() -> RASPFinding {
        var detected = false
        var details = "Corriendo sobre un dispositivo iOS físico real."
        
        #if targetEnvironment(simulator)
        detected = true
        details = "Macro de compilación targetEnvironment(simulator) de Apple activa."
        #else
        // Doble verificación en tiempo de ejecución de las variables de entorno del Simulador
        let environment = ProcessInfo.processInfo.environment
        if environment["SIMULATOR_DEVICE_NAME"] != nil ||
            environment["SIMULATOR_HOST_HOME"] != nil ||
            environment["SIMULATOR_SHARED_RESOURCES_DIRECTORY"] != nil {
            detected = true
            details = "Variables de entorno de simulación activas en el proceso."
        }
        #endif
        
        return RASPFinding(
            checkName = "Anti-Emulator Environment Check",
            isDetected: detected,
            severity: "HIGH",
            details: details
        )
    }
}
