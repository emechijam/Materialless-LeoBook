// update_service.dart: In-app update checker + downloader via Supabase Storage.
// Part of LeoBook App — Services
//
// Checks app-releases/metadata.json for newer APK versions.
// Downloads APK in-app with progress, then triggers Android installer.

import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:dio/dio.dart';
import 'package:device_info_plus/device_info_plus.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:open_filex/open_filex.dart';
import 'package:path_provider/path_provider.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

// ── State ────────────────────────────────────────────────────────────────────

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

class UpdateState {
  final AppUpdateInfo info;
  final UpdateDownloadState downloadState;
  final double downloadProgress;
  final String? errorMessage;

  const UpdateState({
    this.info = const AppUpdateInfo(),
    this.downloadState = UpdateDownloadState.idle,
    this.downloadProgress = 0.0,
    this.errorMessage,
  });

  UpdateState copyWith({
    AppUpdateInfo? info,
    UpdateDownloadState? downloadState,
    double? downloadProgress,
    String? errorMessage,
  }) =>
      UpdateState(
        info: info ?? this.info,
        downloadState: downloadState ?? this.downloadState,
        downloadProgress: downloadProgress ?? this.downloadProgress,
        errorMessage: errorMessage ?? this.errorMessage,
      );
}

// ── Cubit ────────────────────────────────────────────────────────────────────

class UpdateCubit extends Cubit<UpdateState> {
  static const String _bucket = 'app-releases';
  static const String _metadataFile = 'metadata.json';

  Timer? _timer;
  String? _downloadedApkPath;

  static String? _cachedAppVersion;

  UpdateCubit() : super(const UpdateState());

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
    checkForUpdate();
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
      final downloadUrl = await _resolveDownloadUrl(metadata);
      final isNewer = _isVersionNewer(latestVersion, currentVersion);

      emit(state.copyWith(
        info: AppUpdateInfo(
          updateAvailable: isNewer,
          currentVersion: currentVersion,
          latestVersion: latestVersion,
          downloadUrl: downloadUrl,
        ),
      ));
    } catch (e) {
      debugPrint('[UpdateCubit] Check failed: $e');
    }
  }

  /// Download the APK in-app with progress tracking.
  Future<void> downloadAndInstall() async {
    if (state.info.downloadUrl == null) return;
    if (kIsWeb) return;

    emit(state.copyWith(
      downloadState: UpdateDownloadState.downloading,
      downloadProgress: 0.0,
      errorMessage: null,
    ));

    try {
      final dir = await getTemporaryDirectory();
      final filePath = '${dir.path}/LeoBook-v${state.info.latestVersion}.apk';

      final dio = Dio();
      await dio.download(
        state.info.downloadUrl!,
        filePath,
        onReceiveProgress: (received, total) {
          if (total > 0) {
            emit(state.copyWith(downloadProgress: received / total));
          }
        },
      );

      _downloadedApkPath = filePath;
      emit(state.copyWith(downloadState: UpdateDownloadState.downloaded));
      await installDownloadedApk();
    } catch (e) {
      debugPrint('[UpdateCubit] Download failed: $e');
      emit(state.copyWith(
        downloadState: UpdateDownloadState.error,
        errorMessage: _friendlyErrorMessage('Download failed: ${e.toString()}'),
      ));
    }
  }

  /// Open the downloaded APK with Android's package installer.
  Future<void> installDownloadedApk() async {
    if (_downloadedApkPath == null) return;

    final file = File(_downloadedApkPath!);
    if (!await file.exists()) {
      emit(state.copyWith(
        downloadState: UpdateDownloadState.error,
        errorMessage: 'APK file not found',
      ));
      return;
    }

    emit(state.copyWith(downloadState: UpdateDownloadState.installing));

    try {
      final result = await OpenFilex.open(
        _downloadedApkPath!,
        type: 'application/vnd.android.package-archive',
      );

      if (result.type != ResultType.done) {
        emit(state.copyWith(
          downloadState: UpdateDownloadState.error,
          errorMessage: _friendlyErrorMessage(result.message),
        ));
      }
    } catch (e) {
      emit(state.copyWith(
        downloadState: UpdateDownloadState.error,
        errorMessage: _friendlyErrorMessage('Install failed: ${e.toString()}'),
      ));
    }
  }

  /// Reset download state (e.g. after an error, to allow retry).
  void resetDownloadState() {
    emit(state.copyWith(
      downloadState: UpdateDownloadState.idle,
      downloadProgress: 0.0,
      errorMessage: null,
    ));
  }

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

  Future<String?> _resolveDownloadUrl(Map<String, dynamic> metadata) async {
    final directUrl = metadata['apk_url'] as String?;
    final rawApkUrls = metadata['apk_urls'];

    if (kIsWeb || defaultTargetPlatform != TargetPlatform.android) {
      return directUrl;
    }
    if (rawApkUrls is! Map) return directUrl;

    final apkUrls = <String, String>{};
    rawApkUrls.forEach((key, value) {
      final url = value?.toString().trim();
      if (url != null && url.isNotEmpty) apkUrls[key.toString()] = url;
    });

    if (apkUrls.isEmpty) return directUrl;

    try {
      final plugin = DeviceInfoPlugin();
      final androidInfo = await plugin.androidInfo;
      final abiCandidates = <String>[
        ...androidInfo.supported64BitAbis,
        ...androidInfo.supported32BitAbis,
        ...androidInfo.supportedAbis,
        metadata['default_abi']?.toString() ?? '',
        'arm64-v8a',
        'armeabi-v7a',
        'x86_64',
        'universal',
      ];

      for (final abi in abiCandidates) {
        final normalizedAbi = _normalizeAbi(abi);
        if (normalizedAbi == null) continue;
        final matchedUrl = apkUrls[normalizedAbi];
        if (matchedUrl != null && matchedUrl.isNotEmpty) return matchedUrl;
      }
    } catch (e) {
      debugPrint('[UpdateCubit] ABI resolution failed: $e');
    }

    return directUrl ?? apkUrls['universal'] ?? _firstNonEmptyUrl(apkUrls);
  }

  String? _normalizeAbi(String abi) {
    final normalized = abi.trim().toLowerCase();
    if (normalized.isEmpty) return null;
    switch (normalized) {
      case 'arm64-v8a':
      case 'arm64_v8a':
      case 'arm64':
      case 'aarch64':
        return 'arm64-v8a';
      case 'armeabi-v7a':
      case 'armeabi_v7a':
      case 'armeabi':
      case 'armv7':
        return 'armeabi-v7a';
      case 'x86_64':
      case 'x86-64':
      case 'x64':
        return 'x86_64';
      case 'x86':
        return 'x86';
      case 'universal':
      case 'fat':
        return 'universal';
      default:
        return normalized;
    }
  }

  String? _firstNonEmptyUrl(Map<String, String> apkUrls) {
    for (final url in apkUrls.values) {
      if (url.trim().isNotEmpty) return url;
    }
    return null;
  }

  String _friendlyErrorMessage(String? rawMessage) {
    final message = (rawMessage ?? '').trim();
    if (message.isEmpty) return 'Update failed. Please try again.';
    final lower = message.toLowerCase();
    if (lower.contains('conflicts with an existing package') ||
        lower.contains('package conflict') ||
        lower.contains('inconsistent certificates')) {
      return 'This update package was signed differently from the installed LeoBook app. '
          'Please install the latest official release package.';
    }
    if (lower.contains('app not installed')) {
      return 'Android could not install this update package. '
          'Please try the latest official LeoBook release again.';
    }
    return message;
  }

  @override
  Future<void> close() {
    stopPeriodicCheck();
    return super.close();
  }
}
