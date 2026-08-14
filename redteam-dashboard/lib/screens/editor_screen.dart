import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class EditorScreen extends StatefulWidget {
  const EditorScreen({super.key});

  @override
  State<EditorScreen> createState() => _EditorScreenState();
}

class _EditorScreenState extends State<EditorScreen> {
  final TextEditingController _codeController = TextEditingController();
  String _currentFile = 'backend/main.py';

  final Map<String, String> _mockFiles = {
    'backend/main.py': 'from fastapi import FastAPI\n\napp = FastAPI()\n\n@app.get("/health")\ndef health():\n    return {"status": "ok"}\n\n# TODO: Implementar validación HMAC (A5) y Nonce (A6)',
    'backend/security.py': 'import hmac\nimport hashlib\n\ndef verify_hmac(payload, signature, secret):\n    expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()\n    return hmac.compare_digest(expected, signature)',
    'docker-compose.yml': 'version: "3.8"\nservices:\n  api:\n    build: .\n    ports:\n      - "8000:8000"\n    environment:\n      - SOURCESEAL_KEY=your_secret_key',
  };

  @override
  void initState() {
    super.initState();
    _codeController.text = _mockFiles[_currentFile] ?? '';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_currentFile, style: const TextStyle(fontFamily: 'monospace', fontSize: 14)),
        actions: [
          IconButton(
            icon: const Icon(Icons.save, color: Colors.greenAccent),
            onPressed: () {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('💾 Archivo guardado en el servidor'), backgroundColor: Colors.green),
              );
              // Aquí iría la llamada POST a tu API para guardar el archivo real
            },
          ),
        ],
      ),
      body: Column(
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            color: const Color(0xFF1A1F3A),
            child: DropdownButton<String>(
              value: _currentFile,
              dropdownColor: const Color(0xFF1A1F3A),
              style: const TextStyle(color: Colors.white),
              underline: const SizedBox(),
              items: _mockFiles.keys.map((file) {
                return DropdownMenuItem(value: file, child: Text(file, style: const TextStyle(fontFamily: 'monospace')));
              }).toList(),
              onChanged: (val) {
                setState(() {
                  _currentFile = val!;
                  _codeController.text = _mockFiles[_currentFile] ?? '';
                });
              },
            ),
          ),
          Expanded(
            child: Container(
              color: const Color(0xFF0D1117),
              padding: const EdgeInsets.all(12),
              child: TextField(
                controller: _codeController,
                maxLines: null,
                keyboardType: TextInputType.multiline,
                style: GoogleFonts.firaCode(
                  color: Colors.greenAccent,
                  fontSize: 14,
                  height: 1.4,
                ),
                decoration: const InputDecoration(
                  border: InputBorder.none,
                  hintText: '# Escribe o modifica el código aquí...',
                  hintStyle: TextStyle(color: Colors.white30),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}