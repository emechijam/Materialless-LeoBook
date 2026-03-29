// update_service.dart: In-app update checker + downloader via Supabase Storage.
// Part of LeoBook App — Services
//
// Checks app-releases/metadata.json for newer APK versions.
// Downloads APK in-app with progress, then triggers Android installer.

import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:open_filex/open_filex.dart';
import 'package:path_provider/path_provider.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:package_info_plus/package_info_plus.dart';

class AppUpdateInfo {
  final bool updateAvailable;
  final String currentVersion;
  final String latestVersion;
  final String? downloadUrl;

  const AppUpdateInfo({
    this.updateAvailable = false,
    this.currentVersion = '',
    this.latestVersion = '',
    this.downloadUrl,
  });
}

enum UpdateDownloadState { idle, downloading, downloaded, installing, error }

class UpdateService extends ChangeNotifier {
  static const String _bucket = 'app-releases';
  static const String _metadataFile = 'metadata.json';

  AppUpdateInfo _info = const AppUpdateInfo();
  AppUpdateInfo get info => _info;

  UpdateDownloadState _downloadState = UpdateDownloadState.idle;
  UpdateDownloadState get downloadState => _downloadState;

  double _downloadProgress = 0.0;
  double get downloadProgress => _downloadProgress;

  String? _errorMessage;
  String? get errorMessage => _errorMessage;

  String? _downloadedApkPath;

  Timer? _timer;

  static String? _cachedAppVersion;

  /// Dynamically fetches current app version from pubspec.yaml.
  static Future<String> getAppVersion() async {
    if (_cachedAppVersion != null) return _cachedAppVersion!;
    try {
      final info = await PackageInfo.fromPlatform();
      _cachedAppVersion = info.version;
      return _cachedAppVersion!;
    } catch (e) {
      throw Exception('Failed to dynamically fetch app version: $e');
    }
  }

  /// Start periodic checking (every [intervalSeconds]).
  void startPeriodicCheck({int intervalSeconds = 3}) {
    checkForUpdate(); // Immediate first check
    _timer?.cancel();
    _timer = Timer.periodic(
      Duration(seconds: intervalSeconds),
      (_) => checkForUpdate(),
    );
  }

  void stopPeriodicCheck() {
    _timer?.cancel();
    _timer = null;
  }

  /// Fetch metadata.json from Supabase Storage and compare versions.
  Future<void> checkForUpdate() async {
    try {
      final currentVersion = await getAppVersion();
      final supabase = Supabase.instance.client;

      final bytes = await supabase.storage
          .from(_bucket)
          .download(_metadataFile);

      final jsonStr = utf8.decode(bytes);
      final Map<String, dynamic> metadata = json.decode(jsonStr);

      final latestVersion = metadata['version'] as String? ?? currentVersion;
      final downloadUrl = metadata['apk_url'] as String?;

      final isNewer = _isVersionNewer(latestVersion, currentVersion);

      _info = AppUpdateInfo(
        updateAvailable: isNewer,
        currentVersion: currentVersion,
        latestVersion: latestVersion,
        downloadUrl: downloadUrl,
      );
      notifyListeners();
    } catch (e) {
      debugPrint('[UpdateService] Check failed: $e');
    }
  }

  /// Download the APK in-app with progress tracking.
  Future<void> downloadAndInstall() async {
    if (_info.downloadUrl == null) return;
    if (kIsWeb) return; // Not applicable on web

    _downloadState = UpdateDownloadState.downloading;
    _downloadProgress = 0.0;
    _errorMessage = null;
    notifyListeners();

    try {
      final dir = await getTemporaryDirectory();
      final filePath = '${dir.path}/LeoBook-v${_info.latestVersion}.apk';

      final dio = Dio();
      await dio.download(
        _info.downloadUrl!,
        filePath,
        onReceiveProgress: (received, total) {
          if (total > 0) {
            _downloadProgress = received / total;
            notifyListeners();
          }
        },
      );

      _downloadedApkPath = filePath;
      _downloadState = UpdateDownloadState.downloaded;
      notifyListeners();

      // Auto-trigger install
      await installDownloadedApk();
    } catch (e) {
      debugPrint('[UpdateService] Download failed: $e');
      _downloadState = UpdateDownloadState.error;
      _errorMessage = 'Download failed: ${e.toString()}';
      notifyListeners();
    }
  }

  /// Open the downloaded APK with Android's package installer.
  Future<void> installDownloadedApk() async {
    if (_downloadedApkPath == null) return;

    final file = File(_downloadedApkPath!);
    if (!await file.exists()) {
      _downloadState = UpdateDownloadState.error;
      _errorMessage = 'APK file not found';
      notifyListeners();
      return;
    }

    _downloadState = UpdateDownloadState.installing;
    notifyListeners();

    try {
      final result = await OpenFilex.open(
        _downloadedApkPath!,
        type: 'application/vnd.android.package-archive',
      );

      if (result.type != ResultType.done) {
        _downloadState = UpdateDownloadState.error;
        _errorMessage = result.message;
        notifyListeners();
      }
    } catch (e) {
      _downloadState = UpdateDownloadState.error;
      _errorMessage = 'Install failed: ${e.toString()}';
      notifyListeners();
    }
  }

  /// Reset download state (e.g. after an error, to allow retry).
  void resetDownloadState() {
    _downloadState = UpdateDownloadState.idle;
    _downloadProgress = 0.0;
    _errorMessage = null;
    notifyListeners();
  }

  /// Compare semantic versions: returns true if [remote] > [local].
  bool _isVersionNewer(String remote, String local) {
    final rParts = remote.split('.').map(int.tryParse).toList();
    final lParts = local.split('.').map(int.tryParse).toList();

    for (int i = 0; i < 3; i++) {
      final r = (i < rParts.length ? rParts[i] : 0) ?? 0;
      final l = (i < lParts.length ? lParts[i] : 0) ?? 0;
      if (r > l) return true;
      if (r < l) return false;
    }
    return false;
  }

  @override
  void dispose() {
    stopPeriodicCheck();
    super.dispose();
  }
}
