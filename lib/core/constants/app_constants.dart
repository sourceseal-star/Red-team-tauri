class AppConstants {
  static const String appName = 'SourceSeal Console';
  static const String appVersion = '2.0.0';
  static const String apiBaseUrl = 'http://localhost:8000/api';
  static const String wsBaseUrl = 'ws://localhost:8000/ws';

  static const String scanPort = '/scan/port';
  static const String scanCameras = '/scan/cameras';
  static const String scanRadio = '/scan/radio';
  static const String scanIoT = '/scan/iot';
  static const String scanResults = '/scan/results';
  static const String scanHistory = '/scan/history';
  static const String c2Sessions = '/c2/sessions';
  static const String exploitsList = '/exploits/list';
  static const String exploitsRun = '/exploits/run';
  static const String reportGenerate = '/report/generate';

  static const int connectionTimeout = 30000;
  static const int receiveTimeout = 30000;

  static const String apiUrlKey = 'api_base_url';
  static const String authTokenKey = 'auth_token';
  static const String themeKey = 'app_theme';
}
