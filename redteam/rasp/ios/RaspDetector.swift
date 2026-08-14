import Foundation
import MachO
import Security

#if canImport(Darwin)
import Darwin
#endif

public struct RaspFinding {
    public let severity: String // "critical", "high", "medium"
    public let type: String
    public let detail: String
    public let timestamp: Date
    
    public init(severity: String, type: String, detail: String) {
        self.severity = severity
        self.type = type
        self.detail = detail
        self.timestamp = Date()
    }
    
    public func toDictionary() -> [String: Any] {
        return [
            "severity": severity,
            "type": type,
            "detail": detail,
            "timestamp": Int64(timestamp.timeIntervalSince1970 * 1000)
        ]
    }
}

public class RaspDetector {
    public static let shared = RaspDetector()
    
    private init() {}
    
    public func performAllChecks() -> [RaspFinding] {
        var findings = [RaspFinding]()
        
        // 1. Jailbreak Detection
        if isDeviceJailbroken() {
            findings.append(RaspFinding(
                severity: "critical",
                type: "jailbreak_detected",
                detail: "Suspicious file paths, directory write access, or URL schemes indicate a jailbroken environment."
            ))
        }
        
        // 2. Debugger Detection
        if isDebuggerAttached() {
            findings.append(RaspFinding(
                severity: "critical",
                type: "debugger_detected",
                detail: "An active debugger was detected attached to the running process."
            ))
        }
        
        // 3. Frida Detection
        if checkLoadedLibrariesForFrida() || checkFridaPort() {
            findings.append(RaspFinding(
                severity: "critical",
                type: "frida_detected",
                detail: "Frida runtime libraries or open socket interfaces were detected."
            ))
        }
        
        // 4. Emulator Detection
        if isRunningOnSimulator() {
            findings.append(RaspFinding(
                severity: "high",
                type: "emulator_detected",
                detail: "The application is running inside a virtual simulator/emulator environment."
            ))
        }
        
        // 5. Repackaging Detection
        if !verifyCodeSignature() {
            findings.append(RaspFinding(
                severity: "critical",
                type: "repackaging_detected",
                detail: "Static bundle code signature verification failed, indicating possible code modification or repackaging."
            ))
        }
        
        return findings
    }
    
    // MARK: - Jailbreak Detection Helpers
    
    private func isDeviceJailbroken() -> Bool {
        // Check for common jailbreak files
        let jailbreakPaths = [
            "/Applications/Cydia.app",
            "/Library/MobileSubstrate/MobileSubstrate.dylib",
            "/bin/bash",
            "/usr/sbin/sshd",
            "/etc/apt",
            "/usr/bin/ssh",
            "/private/var/lib/apt/",
            "/private/var/lib/cydia",
            "/private/var/tmp/cydia.log"
        ]
        
        for path in jailbreakPaths {
            if FileManager.default.fileExists(atPath: path) {
                return true
            }
        }
        
        // Check if we can write to restricted system folder
        let jailbreakTestString = "Jailbreak Test"
        do {
            try jailbreakTestString.write(toFile: "/private/jailbreak_test.txt", atomically: true, encoding: .utf8)
            // If write succeeded, we have root/write bypass
            try? FileManager.default.removeItem(atPath: "/private/jailbreak_test.txt")
            return true
        } catch {
            // Succeeded in keeping sandboxed (safe)
        }
        
        return false
    }
    
    // MARK: - Debugger Detection Helpers
    
    private func isDebuggerAttached() -> Bool {
        var info = kinfo_proc()
        var size = MemoryLayout.size(ofValue: info)
        var mib: [Int32] = [CTL_KERN, KERN_PROC, KERN_PROC_PID, getpid()]
        let junk = sysctl(&mib, u_int(mib.count), &info, &size, nil, 0)
        if junk != 0 {
            return false
        }
        return (info.kp_proc.p_flag & P_TRACED) != 0
    }
    
    // MARK: - Frida Detection Helpers
    
    private func checkLoadedLibrariesForFrida() -> Bool {
        let imageCount = _dyld_image_count()
        for i in 0..<imageCount {
            if let imageName = _dyld_get_image_name(i) {
                let name = String(cString: imageName)
                if name.lowercased().contains("frida") || name.lowercased().contains("gadget") {
                    return true
                }
            }
        }
        return false
    }
    
    private func checkFridaPort() -> Bool {
        var socketAddress = sockaddr_in()
        socketAddress.sin_family = sa_family_t(AF_INET)
        socketAddress.sin_port = UInt16(27042).bigEndian
        socketAddress.sin_addr.s_addr = inet_addr("127.0.0.1")
        
        let sock = socket(AF_INET, SOCK_STREAM, 0)
        if sock < 0 {
            return false
        }
        defer {
            close(sock)
        }
        
        let result = withUnsafePointer(to: &socketAddress) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                connect(sock, $0, socklen_t(MemoryLayout<sockaddr_in>.size))
            }
        }
        return result == 0
    }
    
    // MARK: - Emulator Detection Helpers
    
    private func isRunningOnSimulator() -> Bool {
        #if targetEnvironment(simulator)
        return true
        #else
        let environment = ProcessInfo.processInfo.environment
        if environment["SIMULATOR_UDID"] != nil || environment["SIMULATOR_DEVICE_NAME"] != nil {
            return true
        }
        
        var size = 0
        sysctlbyname("machdep.cpu.brand_string", nil, &size, nil, 0)
        if size > 0 {
            var brand = [CChar](repeating: 0, count: size)
            sysctlbyname("machdep.cpu.brand_string", &brand, &size, nil, 0)
            let brandString = String(cString: brand)
            if brandString.contains("Intel") || brandString.contains("AMD") {
                return true
            }
        }
        return false
        #endif
    }
    
    // MARK: - Repackaging Detection Helpers
    
    private func verifyCodeSignature() -> Bool {
        var selfCode: SecCode?
        guard SecCodeCopySelf(SecCSFlags(rawValue: 0), &selfCode) == errSecSuccess, let code = selfCode else {
            return false
        }
        
        var staticCode: SecStaticCode?
        guard SecCodeCopyStaticCode(code, SecCSFlags(rawValue: 0), &staticCode) == errSecSuccess, let sCode = staticCode else {
            return false
        }
        
        let status = SecStaticCodeCheckValidity(sCode, SecCSFlags(rawValue: 0), nil)
        return status == errSecSuccess
    }
}
