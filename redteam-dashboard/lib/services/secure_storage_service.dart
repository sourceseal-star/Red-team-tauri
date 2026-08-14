import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:logger/logger.dart';

class SecureStorageService {
  final FlutterSecureStorage _storage = const FlutterSecureStorage();
  final Logger _logger = Logger();

  Future<void> init() async {
    try {
      await _storage.readAll();
      _logger.i('SecureStorage initialized');
    } catch (e) {
      _logger.e('SecureStorage init error: $e');
    }
  }

  Future<String?> read({required String key}) async {
    try {
      return await _storage.read(key: key);
    } catch (e) {
      _logger.e('SecureStorage read error ($key): $e');
      return null;
    }
  }

  Future<void> write({required String key, required String value}) async {
    try {
      await _storage.write(key: key, value: value);
    } catch (e) {
      _logger.e('SecureStorage write error ($key): $e');
    }
  }

  Future<void> delete({required String key}) async {
    try {
      await _storage.delete(key: key);
    } catch (e) {
      _logger.e('SecureStorage delete error ($key): $e');
    }
  }

  Future<void> deleteAll() async {
    try {
      await _storage.deleteAll();
    } catch (e) {
      _logger.e('SecureStorage deleteAll error: $e');
    }
  }
}
