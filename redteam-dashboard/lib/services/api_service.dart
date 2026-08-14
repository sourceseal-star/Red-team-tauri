import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:crypto/crypto.dart';
import 'package:uuid/uuid.dart';
import '../config/app_config.dart';
import '../services/secure_storage_service.dart';
import 'package:logger/logger.dart';

class ApiService {
  final AppConfig config;
  final SecureStorageService storage;
  final Logger _logger = Logger();

  ApiService(this.config, this.storage);

  // Genera firma HMAC y Nonce para prevenir Replay Attacks (Falla A6) y validar firma (Falla A5)
  Map<String, String> _getSecureHeaders(String body) {
    final nonce = const Uuid().v4();
    final timestamp = DateTime.now().millisecondsSinceEpoch.toString();
    
    // Firma HMAC (Simulada con una clave almacenada de forma segura)
    final secretKey = config.apiKey.isNotEmpty ? config.apiKey : 'default_enterprise_key';
    final payload = '$nonce$timestamp$body';
    final hmacSha256 = Hmac(sha256, utf8.encode(secretKey));
    final signature = hmacSha256.convert(utf8.encode(payload)).toString();

    return {
      'Content-Type': 'application/json',
      'X-Nonce': nonce,
      'X-Timestamp': timestamp,
      'X-Signature': signature,
      'Authorization': 'Bearer ${config.apiKey}',
    };
  }

  Future<Map<String, dynamic>> getHealth() async {
    try {
      final response = await http.get(
        Uri.parse(config.healthEndpoint),
        headers: _getSecureHeaders(''),
      ).timeout(Duration(seconds: config.timeoutSeconds));

      if (response.statusCode == 200) {
        return json.decode(response.body);
      } else {
        _logger.e('Health check failed: ${response.statusCode}');
        return {'status': 'error', 'message': 'HTTP ${response.statusCode}'};
      }
    } catch (e) {
      _logger.e('Network error: $e');
      return {'status': 'offline', 'message': e.toString()};
    }
  }

  Future<Map<String, dynamic>> executeSoarPlaybook(String playbookName) async {
    try {
      final body = json.encode({'playbook': playbookName, 'target': 'enterprise_scan'});
      final response = await http.post(
        Uri.parse('${config.apiBase}/soar/execute'),
        headers: _getSecureHeaders(body),
        body: body,
      ).timeout(Duration(seconds: config.timeoutSeconds));

      return json.decode(response.body);
    } catch (e) {
      _logger.e('SOAR execution error: $e');
      return {'status': 'error', 'message': e.toString()};
    }
  }
}