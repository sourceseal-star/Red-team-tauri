import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:google_fonts/google_fonts.dart';
import '../config/app_config.dart';
import '../services/secure_storage_service.dart';

class ConfigScreen extends StatefulWidget {
  const ConfigScreen({super.key});

  @override
  State<ConfigScreen> createState() => _ConfigScreenState();
}

class _ConfigScreenState extends State<ConfigScreen> {
  final _formKey = GlobalKey<FormState>();
  late TextEditingController _backendUrlController;
  late TextEditingController _sshHostController;
  late TextEditingController _sshPortController;
  late TextEditingController _sshUserController;
  late TextEditingController _sshPasswordController;
  late TextEditingController _apiKeyController;

  @override
  void initState() {
    super.initState();
    final config = Provider.of<AppConfig>(context, listen: false);
    _backendUrlController = TextEditingController(text: config.backendUrl);
    _sshHostController = TextEditingController(text: config.sshHost);
    _sshPortController = TextEditingController(text: config.sshPort.toString());
    _sshUserController = TextEditingController(text: config.sshUser);
    _sshPasswordController = TextEditingController();
    _apiKeyController = TextEditingController(text: config.apiKey);
  }

  @override
  void dispose() {
    _backendUrlController.dispose();
    _sshHostController.dispose();
    _sshPortController.dispose();
    _sshUserController.dispose();
    _sshPasswordController.dispose();
    _apiKeyController.dispose();
    super.dispose();
  }

  Future<void> _saveConfig() async {
    if (_formKey.currentState!.validate()) {
      final config = Provider.of<AppConfig>(context, listen: false);
      final storage = Provider.of<SecureStorageService>(context, listen: false);

      config.backendUrl = _backendUrlController.text.trim();
      config.sshHost = _sshHostController.text.trim();
      config.sshPort = int.tryParse(_sshPortController.text) ?? 22;
      config.sshUser = _sshUserController.text.trim();
      config.apiKey = _apiKeyController.text.trim();

      await storage.write(key: 'ssh_password', value: _sshPasswordController.text);
      await config.save(storage);

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('✅ Configuración guardada y encriptada'),
          backgroundColor: Colors.green,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Configuración Enterprise')),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            _buildSectionTitle('🌐 Backend API (Corregir URL del JSON)'),
            const Text(
              '⚠️ El scanner detectó una URL malformada. Asegúrate de usar la URL correcta de Replit o VPS.',
              style: TextStyle(color: Colors.orange, fontSize: 12),
            ),
            const SizedBox(height: 8),
            TextFormField(
              controller: _backendUrlController,
              decoration: const InputDecoration(
                labelText: 'Backend URL',
                hintText: 'https://red-team--sealclient2.replit.app',
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.link),
              ),
              validator: (value) => value!.isEmpty ? 'Requerido' : null,
            ),
            const SizedBox(height: 24),

            _buildSectionTitle('🔑 API Key (Para firma HMAC)'),
            TextFormField(
              controller: _apiKeyController,
              decoration: const InputDecoration(
                labelText: 'Secret Key',
                hintText: 'Clave para firmar peticiones (A5/A6)',
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.key),
              ),
              obscureText: true,
            ),
            const SizedBox(height: 24),

            _buildSectionTitle('💻 Conexión SSH'),
            Row(
              children: [
                Expanded(
                  flex: 2,
                  child: TextFormField(
                    controller: _sshHostController,
                    decoration: const InputDecoration(labelText: 'Host', border: OutlineInputBorder()),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: TextFormField(
                    controller: _sshPortController,
                    decoration: const InputDecoration(labelText: 'Port', border: OutlineInputBorder()),
                    keyboardType: TextInputType.number,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _sshUserController,
              decoration: const InputDecoration(labelText: 'Usuario', border: OutlineInputBorder(), prefixIcon: Icon(Icons.person)),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _sshPasswordController,
              decoration: const InputDecoration(labelText: 'Contraseña / Clave Privada', border: OutlineInputBorder(), prefixIcon: Icon(Icons.lock)),
              obscureText: true,
            ),
            const SizedBox(height: 32),

            ElevatedButton.icon(
              onPressed: _saveConfig,
              icon: const Icon(Icons.save),
              label: const Text('Guardar Configuración Segura', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.blueAccent,
                padding: const EdgeInsets.symmetric(vertical: 16),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSectionTitle(String title) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8.0),
      child: Text(title, style: GoogleFonts.inter(fontSize: 16, fontWeight: FontWeight.bold, color: Colors.blueAccent)),
    );
  }
}