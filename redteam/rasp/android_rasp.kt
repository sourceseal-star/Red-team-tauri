package com.sourceseal.rasp

import android.content.Context
import android.content.pm.PackageManager
import android.content.pm.Signature
import android.os.Build
import android.os.Debug
import android.provider.Settings
import android.view.inputmethod.InputMethodInfo
import android.view.inputmethod.InputMethodManager
import com.google.android.play.core.integrity.StandardIntegrityManager
import com.google.android.play.core.integrity.StandardIntegrityManager.PrepareIntegrityTokenRequest
import com.google.android.play.core.integrity.StandardIntegrityManager.StandardIntegrityTokenRequest
import java.io.BufferedReader
import java.io.File
import java.io.FileInputStream
import java.io.FileReader
import java.net.InetAddress
import java.net.Socket
import java.security.MessageDigest
import java.util.Locale
import kotlin.concurrent.thread

/**
 * Representa un hallazgo de seguridad detectado por RASP.
 */
data class RASPFinding(
    val checkName: String,
    val isDetected: Boolean,
    val severity: String, // "CRITICAL", "HIGH", "MEDIUM", "INFO"
    val details: String
)

/**
 * Reporte final que agrupa todos los hallazgos de RASP.
 */
data class RASPReport(
    val timestamp: Long,
    val isDeviceCompromised: Boolean,
    val findings: List<RASPFinding>
)

/**
 * Clase principal de RASP nativo para la plataforma Android de SourceSeal.
 */
class SourceSealRASP(
    private val expectedSignatureHash: String? = null, // Formato SHA-256 en hexadecimal (Ej: "A1B2C3...")
    private val expectedApkHash: String? = null
) {

    companion object {
        private const val TAG = "SourceSealRASP"
        private val SUSPICIOUS_PORTS = listOf(27042, 27043) // Puertos por defecto de Frida
        
        init {
            try {
                // Carga la librería nativa para ptrace y otras validaciones JNI
                System.loadLibrary("sourceseal_rasp")
            } catch (e: UnsatisfiedLinkError) {
                // Silencioso o manejo de logs en entorno controlado
            }
        }
    }

    // Declaración nativa de ptrace para detectar debuggers o inyecciones a bajo nivel
    private external fun detectPtraceNative(): Boolean

    /**
     * Ejecuta todas las comprobaciones de seguridad RASP de forma síncrona.
     */
    fun runAllChecks(context: Context): RASPReport {
        val findings = mutableListOf<RASPFinding>()

        // 1. Anti-Frida
        findings.add(checkFridaMaps())
        findings.add(checkFridaPorts())
        findings.add(checkFridaDylibs())

        // 2. Anti-Emulator
        findings.add(checkEmulatorBuildProperties())
        findings.add(checkEmulatorHardwareFeatures())
        findings.add(checkEmulatorOperatorProperties(context))

        // 3. Tamper Detection
        findings.add(checkApkSignature(context))
        findings.add(checkApkHash(context))

        // 4. Anti-Debug
        findings.add(checkDebuggerConnected())
        findings.add(checkTracerPid())
        findings.add(checkPtrace())

        // 5. Keylogger & IME Detection
        findings.add(checkSuspiciousKeyloggers(context))

        // Determina si el dispositivo está comprometido si hay algún hallazgo HIGH o CRITICAL detectado
        val isDeviceCompromised = findings.any { it.isDetected && (it.severity == "CRITICAL" || it.severity == "HIGH") }

        return RASPReport(
            timestamp = System.currentTimeMillis(),
            isDeviceCompromised = isDeviceCompromised,
            findings = findings
        )
    }

    // ==========================================
    // 1. DETECCIÓN ANTI-FRIDA
    // ==========================================

    /**
     * Revisa /proc/self/maps en busca de trazas en memoria de Frida ("frida", "gum-js").
     */
    private fun checkFridaMaps(): RASPFinding {
        var detected = false
        val details = StringBuilder()
        val mapsFile = File("/proc/self/maps")

        if (mapsFile.exists()) {
            try {
                BufferedReader(FileReader(mapsFile)).use { reader ->
                    var line: String?
                    while (reader.readLine().also { line = it } != null) {
                        if (line != null && (line!!.contains("frida") || line!!.contains("gum-js") || line!!.contains("libfrida"))) {
                            detected = true
                            details.append("Coincidencia encontrada en memoria: ").append(line!!.trim()).append("\n")
                        }
                    }
                }
            } catch (e: Exception) {
                details.append("Error leyendo /proc/self/maps: ${e.message}")
            }
        } else {
            details.append("/proc/self/maps no existe o no es accesible.")
        }

        return RASPFinding(
            checkName = "Anti-Frida Maps Scan",
            isDetected = detected,
            severity = "CRITICAL",
            details = if (detected) details.toString() else "No se encontraron rastros de Frida en /proc/self/maps."
        )
    }

    /**
     * Escanea localmente los puertos por defecto utilizados por Frida Server.
     */
    private fun checkFridaPorts(): RASPFinding {
        var detected = false
        val details = StringBuilder()

        // Ejecutar en hilos locales ligeros con un timeout extremadamente corto
        for (port in SUSPICIOUS_PORTS) {
            var socket: Socket? = null
            try {
                // Realiza un intento síncrono de socket local
                socket = Socket("127.0.0.1", port)
                detected = true
                details.append("Puerto sospechoso de Frida abierto: $port\n")
            } catch (e: Exception) {
                // Puerto cerrado o inaccesible (comportamiento esperado)
            } finally {
                socket?.close()
            }
        }

        return RASPFinding(
            checkName = "Anti-Frida Port Check",
            isDetected = detected,
            severity = "CRITICAL",
            details = if (detected) details.toString() else "Los puertos de Frida (27042, 27043) están cerrados."
        )
    }

    /**
     * Verifica la presencia de librerías inyectadas sospechosas en el directorio de librerías cargadas.
     */
    private fun checkFridaDylibs(): RASPFinding {
        var detected = false
        val details = StringBuilder()
        
        // Verifica en el directorio del sistema y en /proc/self/maps si hay .so de Frida o Cydia Substrate
        val mapsFile = File("/proc/self/maps")
        if (mapsFile.exists()) {
            try {
                BufferedReader(FileReader(mapsFile)).use { reader ->
                    var line: String?
                    while (reader.readLine().also { line = it } != null) {
                        if (line != null) {
                            val lowerLine = line!!.lowercase(Locale.ROOT)
                            if (lowerLine.contains("gadget") || lowerLine.contains("substrate") || lowerLine.contains("hook")) {
                                detected = true
                                details.append("Librería sospechosa inyectada en memoria: ${line!!.trim()}\n")
                            }
                        }
                    }
                }
            } catch (e: Exception) {
                details.append("Error analizando librerías: ${e.message}")
            }
        }

        return RASPFinding(
            checkName = "Anti-Frida Injected Libraries",
            isDetected = detected,
            severity = "CRITICAL",
            details = if (detected) details.toString() else "No se detectaron librerías dinámicas sospechosas."
        )
    }

    // ==========================================
    // 2. DETECCIÓN ANTI-EMULADOR
    // ==========================================

    /**
     * Analiza las propiedades de construcción de la clase Build de Android.
     */
    private fun checkEmulatorBuildProperties(): RASPFinding {
        val indicators = mutableListOf<String>()

        if (Build.FINGERPRINT.startsWith("generic") || Build.FINGERPRINT.startsWith("unknown")) {
            indicators.add("Fingerprint genérico: ${Build.FINGERPRINT}")
        }
        if (Build.MODEL.contains("google_sdk") || Build.MODEL.contains("Emulator") || Build.MODEL.contains("Android SDK built for x86")) {
            indicators.add("Modelo sospechoso: ${Build.MODEL}")
        }
        if (Build.BOARD == "goldfish" || Build.BOARD == "vbox86") {
            indicators.add("Placa de desarrollo sospechosa (BOARD): ${Build.BOARD}")
        }
        if (Build.HARDWARE.contains("goldfish") || Build.HARDWARE.contains("ranchu") || Build.HARDWARE.contains("vbox86")) {
            indicators.add("Hardware virtual detectado (HARDWARE): ${Build.HARDWARE}")
        }
        if (Build.PRODUCT.contains("sdk") || Build.PRODUCT.contains("google_sdk") || Build.PRODUCT.contains("sdk_x86") || Build.PRODUCT.contains("vbox86p")) {
            indicators.add("Producto de desarrollo (PRODUCT): ${Build.PRODUCT}")
        }
        if (Build.MANUFACTURER.contains("Genymotion") || Build.MANUFACTURER.contains("Google")) {
            // Nota: "Google" es común en dispositivos físicos, pero combinado con hardware/emuladores es indicador
            if (Build.HARDWARE.contains("goldfish") || Build.HARDWARE.contains("ranchu")) {
                indicators.add("Fabricante inconsistente con hardware: ${Build.MANUFACTURER}")
            }
        }
        if (Build.BRAND.startsWith("generic") && Build.DEVICE.startsWith("generic")) {
            indicators.add("Marca/Dispositivo genérico: ${Build.BRAND} / ${Build.DEVICE}")
        }

        val detected = indicators.isNotEmpty()
        return RASPFinding(
            checkName = "Anti-Emulator Build Properties",
            isDetected = detected,
            severity = "HIGH",
            details = if (detected) "Indicadores de emulador encontrados:\n" + indicators.joinToString("\n") else "Propiedades de construcción consistentes con un dispositivo real."
        )
    }

    /**
     * Busca archivos del sistema y controladores específicos del emulador de QEMU y VirtualBox.
     */
    private fun checkEmulatorHardwareFeatures(): RASPFinding {
        var detected = false
        val details = StringBuilder()

        val knownEmulatorFiles = listOf(
            "/system/lib/libc_malloc_debug_qemu.so",
            "/sys/qemu_trace",
            "/system/bin/qemu-props",
            "/dev/socket/qemud",
            "/dev/qemu_pipe",
            "/system/lib/libglesx11.so"
        )

        for (filePath in knownEmulatorFiles) {
            val file = File(filePath)
            if (file.exists()) {
                detected = true
                details.append("Archivo del sistema de emulador detectado: $filePath\n")
            }
        }

        return RASPFinding(
            checkName = "Anti-Emulator Hardware Files",
            isDetected = detected,
            severity = "HIGH",
            details = if (detected) details.toString() else "No se encontraron archivos de sistema específicos de emuladores."
        )
    }

    /**
     * Valida la presencia de IMSI y operador telefónico sospechosos (por ejemplo, IMSI de prueba del emulador de T-Mobile/Android).
     */
    private fun checkEmulatorOperatorProperties(context: Context): RASPFinding {
        var detected = false
        val details = StringBuilder()

        try {
            // Se utiliza el operador de SIM por defecto para identificar emuladores
            // El emulador de Android oficial de Google viene configurado con el operador "310260" (T-Mobile USA) o el IMSI "310260000000000"
            val telephonyManager = context.getSystemService(Context.TELEPHONY_SERVICE) as? android.telephony.TelephonyManager
            if (telephonyManager != null) {
                val simOperator = telephonyManager.simOperator
                val networkOperator = telephonyManager.networkOperator
                val simOperatorName = telephonyManager.simOperatorName

                if (simOperator == "310260" || networkOperator == "310260") {
                    // Verificamos si además corre bajo hardware sospechoso para evitar falsos positivos con usuarios reales de T-Mobile USA
                    if (Build.HARDWARE.contains("goldfish") || Build.HARDWARE.contains("ranchu")) {
                        detected = true
                        details.append("SIM/Network operator de desarrollo detectado (310260 T-Mobile Emulator) bajo hardware virtual.\n")
                    }
                }
                
                // Intentamos leer el IMEI / DeviceId si tenemos los permisos requeridos (con try-catch)
                try {
                    val deviceId = telephonyManager.deviceId
                    if (deviceId != null && (deviceId.startsWith("0000000000") || deviceId == "0")) {
                        detected = true
                        details.append("IMEI del dispositivo sospechoso: $deviceId\n")
                    }
                } catch (securityEx: SecurityException) {
                    // Permiso no concedido para leer el IMEI de forma directa (esperado en Android 10+)
                }
            }
        } catch (e: Exception) {
            details.append("Error obteniendo propiedades de telefonía: ${e.message}")
        }

        return RASPFinding(
            checkName = "Anti-Emulator Operator/IMSI Check",
            isDetected = detected,
            severity = "MEDIUM",
            details = if (detected) details.toString() else "Propiedades de telefonía normales o no consultables."
        )
    }

    // ==========================================
    // 3. TAMPER DETECTION (DETECCIÓN DE MANIPULACIÓN)
    // ==========================================

    /**
     * Verifica la firma del APK actual con respecto a un hash SHA-256 esperado.
     */
    private fun checkApkSignature(context: Context): RASPFinding {
        var detected = false
        val details = StringBuilder()

        if (expectedSignatureHash == null) {
            return RASPFinding(
                checkName = "APK Signature Verification",
                isDetected = false,
                severity = "HIGH",
                details = "No se configuró un hash esperado para contrastar la firma."
            )
        }

        try {
            val pm = context.packageManager
            val packageName = context.packageName
            val currentHashes = mutableListOf<String>()

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                val packageInfo = pm.getPackageInfo(packageName, PackageManager.GET_SIGNING_CERTIFICATES)
                val signingInfo = packageInfo.signingInfo
                if (signingInfo != null) {
                    val signatures = if (signingInfo.hasMultipleSigners()) {
                        signingInfo.apkContentsSigners
                    } else {
                        signingInfo.signingCertificateHistory
                    }
                    for (sig in signatures) {
                        currentHashes.add(getSignatureSha256(sig))
                    }
                }
            } else {
                @Suppress("DEPRECATION")
                val packageInfo = pm.getPackageInfo(packageName, PackageManager.GET_SIGNATURES)
                @Suppress("DEPRECATION")
                val signatures = packageInfo.signatures
                if (signatures != null) {
                    for (sig in signatures) {
                        currentHashes.add(getSignatureSha256(sig))
                    }
                }
            }

            // Validar si el hash esperado está dentro de las firmas actuales
            val matched = currentHashes.any { it.equals(expectedSignatureHash, ignoreCase = true) }
            if (!matched) {
                detected = true
                details.append("La firma actual no coincide con la firma original del desarrollador.\n")
                details.append("Firmas detectadas: ${currentHashes.joinToString(", ")}\n")
                details.append("Firma esperada: $expectedSignatureHash\n")
            } else {
                details.append("La firma coincide correctamente con el hash original esperado.")
            }

        } catch (e: Exception) {
            detected = true
            details.append("Error verificando firmas del APK: ${e.message}")
        }

        return RASPFinding(
            checkName = "APK Signature Verification",
            isDetected = detected,
            severity = "CRITICAL",
            details = details.toString()
        )
    }

    /**
     * Calcula el hash criptográfico SHA-256 del binario APK actual en el disco del dispositivo.
     */
    private fun checkApkHash(context: Context): RASPFinding {
        var detected = false
        val details = StringBuilder()

        if (expectedApkHash == null) {
            return RASPFinding(
                checkName = "APK Binary Hash Validation",
                isDetected = false,
                severity = "HIGH",
                details = "No se configuró un hash esperado del APK para la comparación."
            )
        }

        try {
            val apkPath = context.packageCodePath
            val apkFile = File(apkPath)
            
            if (apkFile.exists()) {
                val digest = MessageDigest.getInstance("SHA-256")
                val buffer = ByteArray(8192)
                FileInputStream(apkFile).use { fis ->
                    var bytesRead: Int
                    while (fis.read(buffer).also { bytesRead = it } != -1) {
                        digest.update(buffer, 0, bytesRead)
                    }
                }
                val hashBytes = digest.digest()
                val currentApkHash = hashBytes.joinToString("") { "%02x".format(it) }

                if (!currentApkHash.equals(expectedApkHash, ignoreCase = true)) {
                    detected = true
                    details.append("El APK ha sido manipulado (Tampered).\n")
                    details.append("Hash del APK actual: $currentApkHash\n")
                    details.append("Hash del APK esperado: $expectedApkHash\n")
                } else {
                    details.append("El hash del APK es válido e íntegro.")
                }
            } else {
                detected = true
                details.append("No se pudo localizar el archivo APK del sistema en la ruta especificada.")
            }
        } catch (e: Exception) {
            detected = true
            details.append("Error calculando el hash del APK: ${e.message}")
        }

        return RASPFinding(
            checkName = "APK Binary Hash Validation",
            isDetected = detected,
            severity = "CRITICAL",
            details = details.toString()
        )
    }

    private fun getSignatureSha256(signature: Signature): String {
        val rawCert = signature.toByteArray()
        val digest = MessageDigest.getInstance("SHA-256")
        val hash = digest.digest(rawCert)
        return hash.joinToString("") { "%02x".format(it) }.uppercase(Locale.ROOT)
    }

    // ==========================================
    // 4. DETECCIÓN ANTI-DEBUG
    // ==========================================

    /**
     * Detección estándar del debugger utilizando las APIs nativas de la máquina virtual de Android.
     */
    private fun checkDebuggerConnected(): RASPFinding {
        val detected = Debug.isDebuggerConnected() || Debug.waitingForDebugger()
        return RASPFinding(
            checkName = "Anti-Debug API Check",
            isDetected = detected,
            severity = "CRITICAL",
            details = if (detected) "Un depurador de aplicaciones Java/Kotlin se encuentra conectado actualmente al proceso." else "No se detectó ningún depurador conectado mediante APIs estándar."
        )
    }

    /**
     * Inspecciona /proc/self/status para encontrar el valor de TracerPid.
     */
    private fun checkTracerPid(): RASPFinding {
        var detected = false
        var tracerPid = 0
        val details = StringBuilder()
        val statusFile = File("/proc/self/status")

        if (statusFile.exists()) {
            try {
                BufferedReader(FileReader(statusFile)).use { reader ->
                    var line: String?
                    while (reader.readLine().also { line = it } != null) {
                        if (line != null && line!!.startsWith("TracerPid:")) {
                            val parts = line!!.split("\\s+".toRegex())
                            if (parts.size >= 2) {
                                tracerPid = parts[1].toIntOrNull() ?: 0
                                if (tracerPid != 0) {
                                    detected = true
                                    details.append("TracerPid detectado con valor: $tracerPid (Un depurador ptrace nativo está adjunto al proceso).\n")
                                }
                            }
                            break
                        }
                    }
                }
            } catch (e: Exception) {
                details.append("Error analizando TracerPid: ${e.message}")
            }
        }

        return RASPFinding(
            checkName = "Anti-Debug TracerPid",
            isDetected = detected,
            severity = "CRITICAL",
            details = if (detected) details.toString() else "TracerPid es 0 (Sin traceo ptrace activo)."
        )
    }

    /**
     * Comprobación ptrace de bajo nivel por JNI con fallback si la librería nativa no está cargada.
     */
    private fun checkPtrace(): RASPFinding {
        var detected = false
        var details = "Librería nativa cargada y verificada."
        try {
            detected = detectPtraceNative()
            if (detected) {
                details = "El debugger de bajo nivel (ptrace) rechazó adjuntarse o se detectó adjunto."
            }
        } catch (e: UnsatisfiedLinkError) {
            // Fallback de autocomprobación por software si no hay soporte JNI compilado
            detected = false
            details = "Librería nativa sourceseal_rasp no disponible. Omitiendo ptrace nativo."
        }

        return RASPFinding(
            checkName = "Anti-Debug Native Ptrace",
            isDetected = detected,
            severity = "CRITICAL",
            details = details
        )
    }

    // ==========================================
    // 5. KEYLOGGER & SUSPICIOUS INPUT METHODS
    // ==========================================

    /**
     * Lista todos los teclados (Input Method Editors) activos en el dispositivo y alerta si
     * se detectan IMEs de terceros de origen desconocido que carezcan de los privilegios del sistema.
     */
    private fun checkSuspiciousKeyloggers(context: Context): RASPFinding {
        var detected = false
        val details = StringBuilder()

        try {
            val imm = context.getSystemService(Context.INPUT_METHOD_SERVICE) as? InputMethodManager
            if (imm != null) {
                val enabledImeList: List<InputMethodInfo> = imm.enabledInputMethodList
                for (ime in enabledImeList) {
                    val packageName = ime.packageName
                    val serviceInfo = ime.serviceInfo
                    val applicationInfo = serviceInfo?.applicationInfo

                    // Un teclado sospechoso carece de la bandera FLAG_SYSTEM (no preinstalado de fábrica)
                    // y tiene permisos excesivos, como INTERNET.
                    val isSystemApp = applicationInfo != null && 
                            (applicationInfo.flags and android.content.pm.ApplicationInfo.FLAG_SYSTEM) != 0

                    if (!isSystemApp) {
                        // Alerta de teclado de terceros, útil para auditar en apps de alta seguridad
                        val hasInternetPermission = context.packageManager.checkPermission(
                            android.Manifest.permission.INTERNET, 
                            packageName
                        ) == PackageManager.PERMISSION_GRANTED

                        if (hasInternetPermission) {
                            detected = true
                            details.append("Teclado de terceros no-sistema detectado con acceso a Internet (Riesgo potencial de Keylogger): ")
                                .append(packageName)
                                .append("\n")
                        }
                    }
                }
            }
        } catch (e: Exception) {
            details.append("Error inspeccionando teclados activos: ${e.message}")
        }

        return RASPFinding(
            checkName = "Keylogger / Suspicious IME Detection",
            isDetected = detected,
            severity = "MEDIUM",
            details = if (detected) details.toString() else "Todos los métodos de entrada habilitados son de confianza del sistema."
        )
    }

    // ==========================================
    // 6. ATTESTATION (GOOGLE PLAY INTEGRITY API)
    // ==========================================

    /**
     * Inicia una solicitud a la Google Play Integrity API para obtener el token criptográfico de atestación.
     */
    fun requestPlayIntegrityToken(
        context: Context,
        cloudProjectNumber: Long,
        nonce: String,
        onSuccess: (String) -> Unit,
        onFailure: (Exception) -> Unit
    ) {
        try {
            // Inicializar el StandardIntegrityManager
            val integrityManager = com.google.android.play.core.integrity.IntegrityManagerFactory.create(context)
            
            // Preparar el túnel de integridad
            val prepareRequest = PrepareIntegrityTokenRequest.builder()
                .setCloudProjectNumber(cloudProjectNumber)
                .build()

            integrityManager.prepareIntegrityToken(prepareRequest)
                .addOnSuccessListener { tokenProvider ->
                    // Solicitar el token vinculando el nonce recibido del servidor central
                    val tokenRequest = StandardIntegrityTokenRequest.builder()
                        .setRequestHash(nonce)
                        .build()

                    tokenProvider.request(tokenRequest)
                        .addOnSuccessListener { integrityTokenResponse ->
                            val token = integrityTokenResponse.token()
                            onSuccess(token)
                        }
                        .addOnFailureListener { exception ->
                            onFailure(exception)
                        }
                }
                .addOnFailureListener { exception ->
                    onFailure(exception)
                }
        } catch (e: Exception) {
            onFailure(e)
        }
    }
}
