package rasp.android

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorManager
import android.os.Build
import android.telephony.TelephonyManager
import java.io.BufferedReader
import java.io.File
import java.io.FileReader

enum class DeviceStatus {
    PHYSICAL_DEVICE, EMULATOR_DETECTED, SUSPICIOUS
}

object AntiEmulator {

    fun detectEmulator(context: Context): DeviceStatus {
        var isEmulator = false
        var suspicionCount = 0

        // 1. Build Fingerprint
        val fingerprint = Build.FINGERPRINT
        if (fingerprint.startsWith("generic") ||
            fingerprint.startsWith("unknown") ||
            fingerprint.contains("google_sdk") ||
            fingerprint.contains("Emulator") ||
            fingerprint.contains("Android SDK built for x86") ||
            fingerprint.contains("sdk_google")
        ) {
            isEmulator = true
        }

        // 2. Build Model
        val model = Build.MODEL
        if (model.contains("google_sdk") ||
            model.contains("Emulator") ||
            model.contains("Android SDK built for x86") ||
            model.contains("SDK") ||
            model.contains("Genymotion")
        ) {
            isEmulator = true
        }

        // 3. Build Manufacturer
        val manufacturer = Build.MANUFACTURER
        if (manufacturer.contains("Genymotion") || 
            manufacturer.contains("Google") && Build.HARDWARE.contains("goldfish")
        ) {
            isEmulator = true
        }

        // 4. Hardware/Product/Device properties
        val hardware = Build.HARDWARE
        val product = Build.PRODUCT
        val device = Build.DEVICE
        if (hardware == "goldfish" || hardware == "ranchu" || hardware == "vbox86" || hardware.contains("nofp")) {
            isEmulator = true
        }
        if (product.contains("sdk") || product.contains("sdk_google") || product.contains("google_sdk") || product.contains("vbox86")) {
            isEmulator = true
        }
        if (device.contains("generic") || device.contains("vbox86")) {
            isEmulator = true
        }

        // 5. /proc/cpuinfo check for 'goldfish' or 'ranchu'
        if (checkCpuInfoForEmulator()) {
            isEmulator = true
        }

        // 6. Check sensor presence (physical devices usually have accelerometer/gyroscope, emulators often don't unless explicitly added)
        val sensorManager = context.getSystemService(Context.SENSOR_SERVICE) as? SensorManager
        if (sensorManager != null) {
            val hasAccelerometer = sensorManager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER) != null
            val hasGyroscope = sensorManager.getDefaultSensor(Sensor.TYPE_GYROSCOPE) != null
            if (!hasAccelerometer || !hasGyroscope) {
                suspicionCount++
            }
        } else {
            suspicionCount++
        }

        // 7. Telephony default IMSI / Operator check
        val telephonyManager = context.getSystemService(Context.TELEPHONY_SERVICE) as? TelephonyManager
        if (telephonyManager != null) {
            val operatorName = telephonyManager.networkOperatorName
            if (operatorName.lowercase() == "android") {
                suspicionCount++
            }
            try {
                // IMSI checking might require permissions, so wrap in safe call
                @Suppress("DEPRECATION")
                val subscriberId = telephonyManager.subscriberId
                if (subscriberId != null && (subscriberId.startsWith("310260000000000") || subscriberId == "404000000000000")) {
                    isEmulator = true
                }
            } catch (e: SecurityException) {
                // Permission denied, skip subscriber ID check
            }
        }

        if (isEmulator) {
            return DeviceStatus.EMULATOR_DETECTED
        }
        if (suspicionCount >= 2) {
            return DeviceStatus.SUSPICIOUS
        }
        return DeviceStatus.PHYSICAL_DEVICE
    }

    private fun checkCpuInfoForEmulator(): Boolean {
        try {
            val cpuInfoFile = File("/proc/cpuinfo")
            if (cpuInfoFile.exists()) {
                BufferedReader(FileReader(cpuInfoFile)).use { reader ->
                    var line: String?
                    while (reader.readLine().also { line = it } != null) {
                        val currentLine = line?.lowercase() ?: continue
                        if (currentLine.contains("goldfish") || currentLine.contains("ranchu")) {
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
}
