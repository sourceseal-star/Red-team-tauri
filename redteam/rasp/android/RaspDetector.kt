package rasp.android

import android.content.Context
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.io.File
import java.io.FileReader
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

data class Finding(
    val severity: String, // "CRITICAL", "HIGH", "MEDIUM"
    val type: String,
    val detail: String,
    val timestamp: Long = System.currentTimeMillis()
) {
    fun toJsonObject(): JSONObject {
        val json = JSONObject()
        json.put("severity", severity)
        json.put("type", type)
        json.put("detail", detail)
        json.put("timestamp", timestamp)
        return json
    }
}

object RaspDetector {
    private val scope = CoroutineScope(Dispatchers.IO)
    private var isInitialized = false
    private lateinit var backendUrl: String
    private lateinit var expectedSignatureHash: String
    private lateinit var deviceId: String

    fun initialize(
        context: Context,
        backendUrl: String,
        expectedSignatureHash: String,
        deviceId: String
    ) {
        if (isInitialized) return
        this.backendUrl = backendUrl
        this.expectedSignatureHash = expectedSignatureHash
        this.deviceId = deviceId
        this.isInitialized = true

        // Run checks at startup asynchronously
        scope.launch {
            runAndReportChecks(context.applicationContext)
        }
    }

    suspend fun runAndReportChecks(context: Context): List<Finding> {
        val findings = mutableListOf<Finding>()

        // 1. Frida detection
        val fridaStatus = AntiFrida.detectFrida()
        if (fridaStatus == FridaStatus.DETECTED) {
            findings.add(Finding("CRITICAL", "FRIDA_DETECTED", "Frida instrumentation framework was found active on the device."))
        } else if (fridaStatus == FridaStatus.SUSPICIOUS) {
            findings.add(Finding("HIGH", "FRIDA_SUSPICIOUS", "Suspicious artifacts indicating possible Frida presence were found."))
        }

        // 2. Emulator detection
        val emulatorStatus = AntiEmulator.detectEmulator(context)
        if (emulatorStatus == DeviceStatus.EMULATOR_DETECTED) {
            findings.add(Finding("HIGH", "EMULATOR_DETECTED", "Application is running on an emulator (virtual device)."))
        } else if (emulatorStatus == DeviceStatus.SUSPICIOUS) {
            findings.add(Finding("MEDIUM", "EMULATOR_SUSPICIOUS", "Device characteristics suggest an emulator environment."))
        }

        // 3. Root/Magisk detection
        if (checkRootAndMagisk()) {
            findings.add(Finding("CRITICAL", "ROOT_DETECTED", "Device is rooted (su binary or Magisk artifacts detected)."))
        }

        // 4. Debugger detection
        if (android.os.Debug.isDebuggerConnected() || checkTracerPid()) {
            findings.add(Finding("CRITICAL", "DEBUGGER_DETECTED", "An active debugger is attached to the process."))
        }

        // 5. Signature verification
        val tamper = TamperDetection(context, expectedSignatureHash)
        if (!tamper.verifySignature()) {
            findings.add(Finding("CRITICAL", "SIGNATURE_VERIFICATION_FAILED", "Application signature does not match the expected production certificate."))
        }

        // 6. Hooking framework detection (Xposed/Substrate)
        if (checkXposed()) {
            findings.add(Finding("CRITICAL", "XPOSED_DETECTED", "Xposed framework classes were detected in the runtime environment."))
        }
        if (checkMapsForHookingLibraries() || checkStackTraceForHooks()) {
            findings.add(Finding("CRITICAL", "HOOKING_FRAMEWORK_DETECTED", "Substrate, Cydia, or Xposed traces were found in process memory or stack traces."))
        }

        // 7. Overlay risk
        if (tamper.isOverlayAttackPossible()) {
            findings.add(Finding("MEDIUM", "OVERLAY_RISK", "Suspicious background non-system Accessibility services are active, making overlay attacks possible."))
        }

        // 8. Debuggable build
        if (tamper.isAppDebuggable()) {
            findings.add(Finding("HIGH", "DEBUGGABLE_BUILD", "The application was compiled with android:debuggable=true."))
        }

        // Report to backend attestation API
        if (findings.isNotEmpty() && this::backendUrl.isInitialized) {
            reportFindingsToBackend(findings)
        }

        return findings
    }

    private fun checkRootAndMagisk(): Boolean {
        val paths = arrayOf(
            "/system/app/Superuser.apk",
            "/sbin/su",
            "/system/bin/su",
            "/system/xbin/su",
            "/data/local/xbin/su",
            "/data/local/bin/su",
            "/system/sd/xbin/su",
            "/system/bin/failsafe/su",
            "/data/local/su",
            "/su/bin/su"
        )
        for (path in paths) {
            if (File(path).exists()) {
                return true
            }
        }
        
        try {
            val process = Runtime.getRuntime().exec(arrayOf("/system/xbin/which", "su"))
            BufferedReader(java.io.InputStreamReader(process.inputStream)).use { reader ->
                if (reader.readLine() != null) return true
            }
        } catch (t: Throwable) {
            // Ignore
        }
        
        val magiskPaths = arrayOf(
            "/sbin/.magisk",
            "/data/adb/magisk",
            "/data/adb/magisk.db"
        )
        for (path in magiskPaths) {
            if (File(path).exists()) {
                return true
            }
        }

        return false
    }

    private fun checkTracerPid(): Boolean {
        try {
            val statusFile = File("/proc/self/status")
            if (statusFile.exists()) {
                BufferedReader(FileReader(statusFile)).use { reader ->
                    var line: String?
                    while (reader.readLine().also { line = it } != null) {
                        if (line?.startsWith("TracerPid:") == true) {
                            val parts = line!!.split("\\s+".toRegex())
                            if (parts.size > 1) {
                                val tracerPid = parts[1].toIntOrNull()
                                if (tracerPid != null && tracerPid != 0) {
                                    return true
                                }
                            }
                        }
                    }
                }
            }
        } catch (e: Exception) {
            // Ignore
        }
        return false
    }

    private fun checkXposed(): Boolean {
        return try {
            Class.forName("de.robv.android.xposed.XposedBridge")
            true
        } catch (e: ClassNotFoundException) {
            false
        } catch (e: Throwable) {
            true
        }
    }

    private fun checkMapsForHookingLibraries(): Boolean {
        try {
            val mapsFile = File("/proc/self/maps")
            if (mapsFile.exists()) {
                BufferedReader(FileReader(mapsFile)).use { reader ->
                    var line: String?
                    while (reader.readLine().also { line = it } != null) {
                        val currentLine = line ?: continue
                        if (currentLine.contains("libsubstrate.so") || 
                            currentLine.contains("libcycript.so") ||
                            currentLine.contains("cydia") ||
                            currentLine.contains("substrate")) {
                            return true
                        }
                    }
                }
            }
        } catch (e: Exception) {
            // Ignore
        }
        return false
    }

    private fun checkStackTraceForHooks(): Boolean {
        try {
            throw Exception("Stack trace check")
        } catch (e: Exception) {
            for (element in e.stackTrace) {
                val className = element.className
                if (className.contains("de.robv.android.xposed.XposedBridge") ||
                    className.contains("com.saurik.substrate.MS") ||
                    className.contains("frida")
                ) {
                    return true
                }
            }
        }
        return false
    }

    private fun reportFindingsToBackend(findings: List<Finding>) {
        try {
            val url = URL(backendUrl)
            val connection = url.openConnection() as HttpURLConnection
            connection.requestMethod = "POST"
            connection.setRequestProperty("Content-Type", "application/json; utf-8")
            connection.setRequestProperty("Accept", "application/json")
            connection.doOutput = true
            connection.connectTimeout = 5000
            connection.readTimeout = 5000

            val payload = JSONObject()
            payload.put("device_id", deviceId)
            payload.put("platform", "android")
            val mockAttestationToken = "mock_play_integrity_jwt_token_for_$deviceId"
            payload.put("attestation_token", mockAttestationToken)

            val findingsArray = JSONArray()
            for (finding in findings) {
                findingsArray.put(finding.toJsonObject())
            }
            payload.put("findings", findingsArray)

            OutputStreamWriter(connection.outputStream, "UTF-8").use { writer ->
                writer.write(payload.toString())
                writer.flush()
            }

            val responseCode = connection.responseCode
            if (responseCode == HttpURLConnection.HTTP_OK) {
                // Success
            }
        } catch (e: Exception) {
            // Silently fail or log for debug purposes
        }
    }
}
