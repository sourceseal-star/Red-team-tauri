import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:google_fonts/google_fonts.dart';
import '../config/app_config.dart';
import '../services/ssh_service.dart';
import '../services/secure_storage_service.dart';

class TerminalScreen extends StatefulWidget {
  const TerminalScreen({super.key});

  @override
  State<TerminalScreen> createState() => _TerminalScreenState();
}

class _TerminalScreenState extends State<TerminalScreen> {
  final SSHService _sshService = SSHService();
  final List<String> _output = ['> SourceSeal Terminal v1.0', '> Escribe "help" para ver comandos o conecta vía SSH.'];
  final TextEditingController _commandController = TextEditingController();
  bool _isConnected = false;
  bool _isConnecting = false;

  Future<void> _toggleConnection() async {
    if (_isConnected) {
      _sshService.disconnect();
      setState(() {
        _isConnected = false;
        _output.add('> Conexión cerrada.');
      });
      return;
    }

    setState(() => _isConnecting = true);
    final config = Provider.of<AppConfig>(context, listen: false);
    final storage = Provider.of<SecureStorageService>(context, listen: false);
    final password = await storage.read(key: 'ssh_password') ?? '';

    final success = await _sshService.connect(config.sshHost, config.sshPort, config.sshUser, password);
    
    setState(() {
      _isConnected = success;
      _isConnecting = false;
      _output.add(success ? '> ✅ Conectado a ${config.sshHost}:${config.sshPort}' : '> ❌ Fallo de conexión. Revisa Config.');
    });
  }

  void _executeCommand(String command) async {
    if (command.trim().isEmpty) return;
    setState(() => _output.add('\$ $command'));
    _commandController.clear();

    if (command == 'clear') {
      setState(() => _output.clear());
      return;
    }

    if (!_isConnected) {
      setState(() => _output.add('> ⚠️ No hay conexión SSH. Conecta primero o usa comandos locales.'));
      return;
    }

    final result = await _sshService.executeCommand(command);
    setState(() => _output.addAll(result.split('\n')));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Terminal SSH'),
        actions: [
          IconButton(
            icon: _isConnecting 
                ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                : Icon(_isConnected ? Icons.link : Icons.link_off, color: _isConnected ? Colors.green : Colors.red),
            onPressed: _toggleConnection,
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: Container(
              width: double.infinity,
              color: const Color(0xFF0D1117),
              padding: const EdgeInsets.all(12),
              child: ListView.builder(
                itemCount: _output.length,
                itemBuilder: (context, index) {
                  final line = _output[index];
                  return SelectableText(
                    line,
                    style: GoogleFonts.firaCode(
                      color: line.startsWith('>') ? (line.contains('✅') ? Colors.green : (line.contains('❌') ? Colors.red : Colors.blueAccent)) : Colors.white70,
                      fontSize: 13,
                    ),
                  );
                },
              ),
            ),
          ),
          Container(
            padding: const EdgeInsets.all(12),
            color: const Color(0xFF1A1F3A),
            child: Row(
              children: [
                const Text('> ', style: TextStyle(color: Colors.greenAccent, fontFamily: 'monospace', fontWeight: FontWeight.bold)),
                Expanded(
                  child: TextField(
                    controller: _commandController,
                    style: const TextStyle(color: Colors.white, fontFamily: 'monospace'),
                    decoration: const InputDecoration(
                      hintText: 'Escribe un comando (ej: docker ps, ufw status)...',
                      border: InputBorder.none,
                    ),
                    onSubmitted: _executeCommand,
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.send, color: Colors.blueAccent),
                  onPressed: () => _executeCommand(_commandController.text),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  @override
  void dispose() {
    _commandController.dispose();
    _sshService.disconnect();
    super.dispose();
  }
}