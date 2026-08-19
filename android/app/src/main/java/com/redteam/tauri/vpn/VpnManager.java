package com.redteam.tauri.vpn;

import android.content.Context;
import android.content.Intent;
import android.net.VpnService;
import android.os.Build;
import android.util.Log;

/**
 * VpnManager - Gestor del servicio VPN
 * ====================================
 * Gestiona la conexión entre VpnService y el backend Python.
 */
public class VpnManager {
    
    private static final String TAG = "ARTO_VpnManager";
    private static VpnManager instance;
    private Context context;
    
    public static synchronized VpnManager getInstance(Context context) {
        if (instance == null) {
            instance = new VpnManager(context.getApplicationContext());
        }
        return instance;
    }
    
    private VpnManager(Context context) {
        this.context = context;
    }
    
    public void startVpnService() {
        Log.d(TAG, "Iniciando servicio VPN...");
        Intent intent = VpnService.prepare(context);
        if (intent != null) {
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            context.startActivity(intent);
        } else {
            Intent serviceIntent = new Intent(context, ARTOVpnService.class);
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(serviceIntent);
            } else {
                context.startService(serviceIntent);
            }
        }
    }
    
    public void stopVpnService() {
        Log.d(TAG, "Deteniendo servicio VPN...");
        Intent serviceIntent = new Intent(context, ARTOVpnService.class);
        context.stopService(serviceIntent);
    }
    
    public void sendPacketToBackend(ARTOVpnService.PacketData packetData) {
        try {
            String json = String.format(
                "{\"src_ip\":\"%s\",\"dst_ip\":\"%s\",\"src_port\":%d,\"dst_port\":%d,\"protocol\":\"%s\",\"length\":%d,\"timestamp\":%d}",
                packetData.srcIp, packetData.dstIp, packetData.srcPort, packetData.dstPort,
                packetData.protocol, packetData.length, packetData.timestamp);
            sendToPythonBackend(json);
        } catch (Exception e) {
            Log.e(TAG, "Error enviando paquete al backend: " + e.getMessage());
        }
    }
    
    private void sendToPythonBackend(String data) {
        Log.d(TAG, "Paquete para backend: " + data);
        // En implementación real con Tauri: usar WebSocket o canal nativo (Rust/JNI)
    }
}
