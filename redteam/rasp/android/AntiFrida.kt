package rasp.android

import java.io.BufferedReader
import java.io.File
import java.io.FileReader
import java.io.IOException
import java.net.InetSocketAddress
import java.net.Socket

enum class FridaStatus {
    SAFE, DETECTED, SUSPICIOUS
}

object AntiFrida {
    
    fun detectFrida(): FridaStatus {
        // 1. Check /proc/self/maps for 'frida', 'frida-gadget', or 'linjector'
        if (checkMapsForFrida()) {
            return FridaStatus.DETECTED
        }
        
        // 2. Check running processes or files for 'frida-server'
        if (checkFridaServerProcess()) {
            return FridaStatus.DETECTED
        }
        
        // 3. TCP scan port 27042 (Frida default)
        if (scanFridaPort(27042)) {
            return FridaStatus.DETECTED
        }
        
        // 4. Checking suspicious system properties
        if (checkSuspiciousProperties()) {
            return FridaStatus.SUSPICIOUS
        }
        
        return FridaStatus.SAFE
    }

    private fun checkMapsForFrida(): Boolean {
        try {
            val mapsFile = File("/proc/self/maps")
            if (mapsFile.exists()) {
                BufferedReader(FileReader(mapsFile)).use { reader ->
                    var line: String?
                    while (reader.readLine().also { line = it } != null) {
                        val currentLine = line ?: continue
                        if (currentLine.contains("frida", ignoreCase = true) || 
                            currentLine.contains("frida-gadget", ignoreCase = true) ||
                            currentLine.contains("linjector", ignoreCase = true)) {
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

    private fun checkFridaServerProcess(): Boolean {
        // Check standard binary existence
        val commonPaths = arrayOf(
            "/data/local/tmp/frida-server",
            "/data/local/tmp/re.frida.server",
            "/sbin/frida-server",
            "/system/bin/frida-server"
        )
        for (path in commonPaths) {
            val file = File(path)
            if (file.exists() && file.canExecute()) {
                return true
            }
        }
        
        // Check running processes via ps
        try {
            val process = Runtime.getRuntime().exec("ps")
            BufferedReader(java.io.InputStreamReader(process.inputStream)).use { reader ->
                var line: String?
                while (reader.readLine().also { line = it } != null) {
                    if (line?.contains("frida-server", ignoreCase = true) == true) {
                        return true
                    }
                }
            }
        } catch (e: Exception) {
            // Ignored
        }
        return false
    }

    private fun scanFridaPort(port: Int): Boolean {
        var socket: Socket? = null
        return try {
            socket = Socket()
            socket.connect(InetSocketAddress("127.0.0.1", port), 100) // 100ms timeout
            true
        } catch (e: Exception) {
            false
        } finally {
            try {
                socket?.close()
            } catch (e: IOException) {
                // Ignore
            }
        }
    }
    
    private fun checkSuspiciousProperties(): Boolean {
        try {
            val properties = listOf("frida.server.port", "re.frida.server")
            for (prop in properties) {
                val value = System.getProperty(prop)
                if (!value.isNullOrEmpty()) {
                    return true
                }
            }
        } catch (e: Exception) {
            // Ignore
        }
        return false
    }
}
