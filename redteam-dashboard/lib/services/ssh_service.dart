import 'package:dartssh2/dartssh2.dart';
import 'package:logger/logger.dart';

class SSHService {
  SSHClient? _client;
  final Logger _logger = Logger();

  Future<bool> connect(String host, int port, String username, String password) async {
    try {
      _logger.i('Conectando a $host:$port como $username...');
      _client = SSHClient(
        await SSHSocket.connect(host, port),
        username: username,
        onPasswordRequest: () => password,
      );
      _logger.i('Conexión SSH establecida');
      return true;
    } catch (e) {
      _logger.e('Error de conexión SSH: $e');
      return false;
    }
  }

  Future<String> executeCommand(String command) async {
    if (_client == null) throw Exception('No hay conexión SSH activa');
    try {
      final result = await _client!.run(command);
      return String.fromCharCodes(result);
    } catch (e) {
      _logger.e('Error ejecutando comando: $e');
      return 'Error: $e';
    }
  }

  void disconnect() {
    _client?.close();
    _client = null;
    _logger.i('Conexión SSH cerrada');
  }

  bool get isConnected => _client != null;
}