import 'dart:async';
import 'dart:convert';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../core/constants/app_constants.dart';

class WebSocketService {
  WebSocketChannel? _channel;
  final _messageController = StreamController<Map<String, dynamic>>.broadcast();
  final _connectionController = StreamController<bool>.broadcast();

  Stream<Map<String, dynamic>> get messages => _messageController.stream;
  Stream<bool> get connectionStatus => _connectionController.stream;

  void connect({String? url}) {
    try {
      _channel = WebSocketChannel.connect(Uri.parse(url ?? AppConstants.wsBaseUrl));
      _connectionController.add(true);

      _channel!.stream.listen(
        (message) {
          final data = jsonDecode(message as String);
          _messageController.add(data);
        },
        onError: (error) {
          _connectionController.add(false);
        },
        onDone: () {
          _connectionController.add(false);
        },
      );
    } catch (e) {
      _connectionController.add(false);
    }
  }

  void send(Map<String, dynamic> data) {
    _channel?.sink.add(jsonEncode(data));
  }

  void disconnect() {
    _channel?.sink.close();
    _channel = null;
    _connectionController.add(false);
  }

  void dispose() {
    disconnect();
    _messageController.close();
    _connectionController.close();
  }
}
