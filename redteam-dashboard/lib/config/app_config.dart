import 'package:flutter/foundation.dart';
import '../services/secure_storage_service.dart';

class AppConfig extends ChangeNotifier {
  String backendUrl;
  String sshHost;
  int sshPort;
  String sshUser;
  String? sshPassword;
  String? sshPrivateKey;
  String apiKey;
  bool autoReconnect;
  int timeoutSeconds;

  AppConfig({
    this.backendUrl = 'https://red-team--sealclient2.replit.app',
    this.sshHost = 'localhost',
    this.sshPort = 22,
    this.sshUser = 'user',
    this.sshPassword,
    this.sshPrivateKey,
    this.apiKey = '',
    this.autoReconnect = true,
    this.timeoutSeconds = 30,
  });

  static Future<AppConfig> load(SecureStorageService storage) async {
    final config = AppConfig();
    config.backendUrl = await storage.read(key: 'backend_url') ?? config.backendUrl;
    config.sshHost = await storage.read(key: 'ssh_host') ?? config.sshHost;
    config.sshPort = int.parse(await storage.read(key: 'ssh_port') ?? '${config.sshPort}');
    config.sshUser = await storage.read(key: 'ssh_user') ?? config.sshUser;
    config.apiKey = await storage.read(key: 'api_key') ?? config.apiKey;
    config.autoReconnect = (await storage.read(key: 'auto_reconnect')) == 'true';
    return config;
  }

  Future<void> save(SecureStorageService storage) async {
    await storage.write(key: 'backend_url', value: backendUrl);
    await storage.write(key: 'ssh_host', value: sshHost);
    await storage.write(key: 'ssh_port', value: '$sshPort');
    await storage.write(key: 'ssh_user', value: sshUser);
    await storage.write(key: 'api_key', value: apiKey);
    await storage.write(key: 'auto_reconnect', value: '$autoReconnect');
    notifyListeners();
  }

  String get healthEndpoint => '$backendUrl/health';
  String get apiBase => '$backendUrl/v1';
  String get attacksEndpoint => '$apiBase/attacks';
  String get vulnerabilitiesEndpoint => '$apiBase/vulnerabilities';
  String get modulesEndpoint => '$apiBase/modules';
  String get logsEndpoint => '$apiBase/logs';
}