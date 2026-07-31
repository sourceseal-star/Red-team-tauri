package rasp.android

import android.accessibilityservice.AccessibilityServiceInfo
import android.content.Context
import android.content.pm.ApplicationInfo
import android.content.pm.PackageManager
import android.os.Build
import android.provider.Settings
import android.view.Window
import android.view.WindowManager
import android.view.accessibility.AccessibilityManager
import java.security.MessageDigest

class TamperDetection(
    private val context: Context,
    private val expectedSignatureHash: String
) {

    /**
     * Verifies the APK's signature by calculating its SHA-256 hash and
     * comparing it against the expected hardcoded signature hash.
     */
    fun verifySignature(): Boolean {
        try {
            val packageName = context.packageName
            val packageManager = context.packageManager
            val signatures = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                val signingInfo = packageManager.getPackageInfo(packageName, PackageManager.GET_SIGNING_CERTIFICATES).signingInfo
                if (signingInfo != null) {
                    if (signingInfo.hasMultipleSigners()) {
                        signingInfo.apkContentsSigners
                    } else {
                        signingInfo.signingCertificateHistory
                    }
                } else {
                    null
                }
            } else {
                @Suppress("DEPRECATION")
                val packageInfo = packageManager.getPackageInfo(packageName, PackageManager.GET_SIGNATURES)
                @Suppress("DEPRECATION")
                packageInfo.signatures
            }

            if (signatures == null || signatures.isEmpty()) {
                return false
            }

            for (sig in signatures) {
                val rawCert = sig.toByteArray()
                val digest = MessageDigest.getInstance("SHA-256")
                val hashBytes = digest.digest(rawCert)
                val computedHash = bytesToHex(hashBytes)
                
                // Compare (case-insensitive)
                if (computedHash.equals(expectedSignatureHash, ignoreCase = true)) {
                    return true
                }
            }
        } catch (e: Exception) {
            // Treat verification exceptions as a verification failure (fail closed)
        }
        return false
    }

    /**
     * Checks if the app is running in debug mode.
     */
    fun isAppDebuggable(): Boolean {
        return try {
            (context.applicationInfo.flags and ApplicationInfo.FLAG_DEBUGGABLE) != 0
        } catch (e: Exception) {
            false
        }
    }

    /**
     * Checks for potential overlay attacks.
     * This checks if active non-system Accessibility Services are running that can manipulate the UI.
     */
    fun isOverlayAttackPossible(): Boolean {
        var suspicious = false
        try {
            val am = context.getSystemService(Context.ACCESSIBILITY_SERVICE) as? AccessibilityManager
            if (am != null && am.isEnabled) {
                val enabledServices = am.getEnabledAccessibilityServiceList(AccessibilityServiceInfo.FEEDBACK_ALL_MASK)
                if (!enabledServices.isNullOrEmpty()) {
                    for (service in enabledServices) {
                        val serviceAppInfo = service.resolveInfo?.serviceInfo?.applicationInfo
                        if (serviceAppInfo != null) {
                            val isSystemApp = (serviceAppInfo.flags and ApplicationInfo.FLAG_SYSTEM) != 0
                            if (!isSystemApp) {
                                suspicious = true
                                break
                            }
                        }
                    }
                }
            }
        } catch (e: Exception) {
            // Ignore
        }
        return suspicious
    }

    /**
     * Checks if the screen capture protection (FLAG_SECURE) is applied to the given window.
     */
    fun isScreenCaptureProtected(window: Window): Boolean {
        val flags = window.attributes.flags
        return (flags and WindowManager.LayoutParams.FLAG_SECURE) != 0
    }

    /**
     * Helper to apply screen capture protection (FLAG_SECURE) to a window.
     */
    fun protectScreenCapture(window: Window) {
        window.setFlags(
            WindowManager.LayoutParams.FLAG_SECURE,
            WindowManager.LayoutParams.FLAG_SECURE
        )
    }

    private fun bytesToHex(bytes: ByteArray): String {
        val sb = StringBuilder()
        for (b in bytes) {
            sb.append(String.format("%02x", b))
        }
        return sb.toString()
    }
}
