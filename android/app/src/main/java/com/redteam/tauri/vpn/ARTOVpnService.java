package com.redteam.tauri.vpn;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Intent;
import android.net.VpnService;
import android.os.Build;
import android.os.ParcelFileDescriptor;
import android.util.Log;

import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;

/**
 * ARTO VpnService - Servicio VPN para captura de tráfico
 * ======================================================
 * Este servicio crea un tunnel VPN que intercepta TODO el tráfico
 * del dispositivo y lo envía al backend Python para análisis.
 */
public class ARTOVpnService extends VpnService {
    
    private static final String TAG = "ARTO_VpnService";
    private static final String CHANNEL_ID = "ARTO_VPN_CHANNEL";
    private static final int NOTIFICATION_ID = 1;
    
    private ParcelFileDescriptor vpnInterface = null;
    private Thread packetCaptureThread = null;
    private volatile boolean running = false;
    private VpnManager vpnManager;
    
    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        Log.d(TAG, "Iniciando VpnService...");
        vpnManager = VpnManager.getInstance(this);
        setupVpn();
        return START_STICKY;
    }
    
    private void setupVpn() {
        try {
            Builder builder = new Builder();
            builder.setSession("ARTO Traffic Capture")
                   .setMtu(1500)
                   .addAddress("10.0.0.2", 24)
                   .addDnsServer("8.8.8.8")
                   .addDnsServer("8.8.4.4")
                   .addRoute("0.0.0.0", 0)
                   .addRoute("::", 0);
            
            vpnInterface = builder.establish();
            
            if (vpnInterface != null) {
                Log.d(TAG, "VPN establecida con éxito");
                showNotification();
                startPacketCapture();
            } else {
                Log.e(TAG, "Fallo al establecer VPN");
                stopSelf();
            }
        } catch (Exception e) {
            Log.e(TAG, "Error al configurar VPN: " + e.getMessage());
            stopSelf();
        }
    }
    
    private void showNotification() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID, "ARTO VPN Service", NotificationManager.IMPORTANCE_LOW);
            NotificationManager manager = getSystemService(NotificationManager.class);
            manager.createNotificationChannel(channel);
        }
        
        Intent notificationIntent = new Intent(this, getClass());
        PendingIntent pendingIntent = PendingIntent.getActivity(
            this, 0, notificationIntent, 
            Build.VERSION.SDK_INT >= Build.VERSION_CODES.M ? PendingIntent.FLAG_IMMUTABLE : 0);
        
        Notification notification = new Notification.Builder(this, CHANNEL_ID)
            .setContentTitle("ARTO VPN")
            .setContentText("Capturando tráfico de red...")
            .setSmallIcon(android.R.drawable.ic_lock_idle_lock)
            .setContentIntent(pendingIntent)
            .build();
        
        startForeground(NOTIFICATION_ID, notification);
    }
    
    private void startPacketCapture() {
        running = true;
        packetCaptureThread = new Thread(() -> capturePackets());
        packetCaptureThread.start();
        Log.d(TAG, "Captura de paquetes iniciada");
    }
    
    private void capturePackets() {
        try {
            FileInputStream in = new FileInputStream(vpnInterface.getFileDescriptor());
            byte[] packet = new byte[4096];
            int bytesRead;
            
            while (running && (bytesRead = in.read(packet)) > 0) {
                processPacket(packet, bytesRead);
            }
        } catch (Exception e) {
            Log.e(TAG, "Error al capturar paquetes: " + e.getMessage());
        } finally {
            stopPacketCapture();
        }
    }
    
    private void processPacket(byte[] packet, int length) {
        try {
            if (length < 20) return;
            
            int versionAndHeaderLength = packet[0] & 0xFF;
            int version = (versionAndHeaderLength >> 4) & 0xF;
            int headerLength = (versionAndHeaderLength & 0xF) * 4;
            
            if (version != 4) return;
            
            String srcIp = String.format("%d.%d.%d.%d",
                packet[12] & 0xFF, packet[13] & 0xFF, packet[14] & 0xFF, packet[15] & 0xFF);
            String dstIp = String.format("%d.%d.%d.%d",
                packet[16] & 0xFF, packet[17] & 0xFF, packet[18] & 0xFF, packet[19] & 0xFF);
            
            int protocol = packet[9] & 0xFF;
            String protocolName;
            int srcPort = 0, dstPort = 0;
            
            switch (protocol) {
                case 6:
                    protocolName = "tcp";
                    if (length >= headerLength + 20) {
                        srcPort = ((packet[headerLength] & 0xFF) << 8) | (packet[headerLength + 1] & 0xFF);
                        dstPort = ((packet[headerLength + 2] & 0xFF) << 8) | (packet[headerLength + 3] & 0xFF);
                    }
                    break;
                case 17:
                    protocolName = "udp";
                    if (length >= headerLength + 8) {
                        srcPort = ((packet[headerLength] & 0xFF) << 8) | (packet[headerLength + 1] & 0xFF);
                        dstPort = ((packet[headerLength + 2] & 0xFF) << 8) | (packet[headerLength + 3] & 0xFF);
                    }
                    break;
                case 1:
                    protocolName = "icmp";
                    break;
                default:
                    protocolName = "unknown";
            }
            
            PacketData packetData = new PacketData();
            packetData.srcIp = srcIp;
            packetData.dstIp = dstIp;
            packetData.srcPort = srcPort;
            packetData.dstPort = dstPort;
            packetData.protocol = protocolName;
            packetData.payload = packet;
            packetData.length = length;
            packetData.timestamp = System.currentTimeMillis();
            
            if (vpnManager != null) {
                vpnManager.sendPacketToBackend(packetData);
            }
        } catch (Exception e) {
            Log.e(TAG, "Error procesando paquete: " + e.getMessage());
        }
    }
    
    private void stopPacketCapture() {
        running = false;
        if (packetCaptureThread != null) {
            try {
                packetCaptureThread.join(500);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
            packetCaptureThread = null;
        }
        Log.d(TAG, "Captura de paquetes detenida");
    }
    
    @Override
    public void onDestroy() {
        Log.d(TAG, "Destruyendo VpnService...");
        stopPacketCapture();
        try {
            if (vpnInterface != null) {
                vpnInterface.close();
                vpnInterface = null;
            }
        } catch (IOException e) {
            Log.e(TAG, "Error cerrando interfaz VPN: " + e.getMessage());
        }
        stopForeground(true);
        super.onDestroy();
    }
    
    public static class PacketData {
        public String srcIp;
        public String dstIp;
        public int srcPort;
        public int dstPort;
        public String protocol;
        public byte[] payload;
        public int length;
        public long timestamp;
    }
}
