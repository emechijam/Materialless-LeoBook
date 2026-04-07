// fingerprint_settings_screen.dart: Per-user session fingerprint viewer.
// Part of LeoBook App — Screens
//
// Displays proxy_server, user_agent, viewport_w/h from the device fingerprint
// service. Read-only for all users — these values are set by device config.

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:leobookapp/core/constants/app_colors.dart';
import 'package:leobookapp/data/services/device_fingerprint_service.dart';

class FingerprintSettingsScreen extends StatefulWidget {
  const FingerprintSettingsScreen({super.key});

  @override
  State<FingerprintSettingsScreen> createState() =>
      _FingerprintSettingsScreenState();
}

class _FingerprintSettingsScreenState
    extends State<FingerprintSettingsScreen> {
  final _service = DeviceFingerprintService();

  bool _loading = true;
  UserDeviceFingerprint? _fp;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    Supabase.instance.client.auth.currentUser?.id ?? '';
    final fp = await _service.load();
    if (mounted) setState(() { _fp = fp; _loading = false; });
  }

  void _copyToClipboard(String value, String label) {
    Clipboard.setData(ClipboardData(text: value));
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text('$label copied'),
      backgroundColor: AppColors.primary,
      duration: const Duration(seconds: 1),
    ));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.neutral900,
      appBar: AppBar(
        backgroundColor: AppColors.neutral900,
        surfaceTintColor: Colors.transparent,
        title: Text(
          'Session Fingerprint',
          style: GoogleFonts.dmSans(
            fontSize: 17,
            fontWeight: FontWeight.w600,
            color: Colors.white,
          ),
        ),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 19),
          onPressed: () => Navigator.of(context).pop(),
        ),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
              children: [
                // ── Info banner ─────────────────────────────────────────
                Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: AppColors.primary.withValues(alpha: 0.06),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                        color: AppColors.primary.withValues(alpha: 0.15)),
                  ),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Icon(Icons.lock_rounded,
                          size: 16, color: AppColors.textTertiary),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          'Session fingerprint is automatically extracted from your device '
                          'and cannot be manually modified. It is used when Leo opens '
                          'Football.com on your behalf.',
                          style: GoogleFonts.dmSans(
                            fontSize: 12,
                            color: AppColors.textTertiary,
                            height: 1.5,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 24),

                _sectionLabel('Session Config'),
                const SizedBox(height: 10),
                _infoCard([
                  _fpRow(
                    icon: Icons.dns_outlined,
                    label: 'Proxy Server',
                    value: _fp?.proxyServer ?? '—  (default)',
                  ),
                  _fpRow(
                    icon: Icons.web_outlined,
                    label: 'User Agent',
                    value: _fp?.userAgent ?? '—  (device default)',
                    multiline: true,
                  ),
                  _fpRow(
                    icon: Icons.aspect_ratio_rounded,
                    label: 'Viewport Width',
                    value: _fp?.viewportW != null
                        ? '${_fp!.viewportW} px'
                        : '390 px (default)',
                  ),
                  _fpRow(
                    icon: Icons.height_rounded,
                    label: 'Viewport Height',
                    value: _fp?.viewportH != null
                        ? '${_fp!.viewportH} px'
                        : '844 px (default)',
                  ),
                ]),
              ],
            ),
    );
  }

  Widget _sectionLabel(String label) => Padding(
        padding: const EdgeInsets.only(left: 2),
        child: Text(
          label,
          style: GoogleFonts.dmSans(
            fontSize: 12,
            fontWeight: FontWeight.w500,
            color: AppColors.textTertiary,
          ),
        ),
      );

  Widget _infoCard(List<Widget> rows) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.neutral800,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.white.withValues(alpha: 0.06)),
      ),
      child: Column(
        children: [
          for (int i = 0; i < rows.length; i++) ...[
            rows[i],
            if (i < rows.length - 1)
              Divider(
                height: 0.5,
                thickness: 0.5,
                color: Colors.white.withValues(alpha: 0.06),
                indent: 16,
              ),
          ],
        ],
      ),
    );
  }

  Widget _fpRow({
    required IconData icon,
    required String label,
    required String value,
    bool multiline = false,
  }) {
    final hasValue = !value.startsWith('—');
    return InkWell(
      onTap: hasValue ? () => _copyToClipboard(value, label) : null,
      borderRadius: BorderRadius.circular(14),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        child: Row(
          crossAxisAlignment:
              multiline ? CrossAxisAlignment.start : CrossAxisAlignment.center,
          children: [
            Icon(icon, size: 16, color: AppColors.textTertiary),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    label,
                    style: GoogleFonts.dmSans(
                      fontSize: 11,
                      color: AppColors.textTertiary,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                  const SizedBox(height: 3),
                  Text(
                    value,
                    style: GoogleFonts.dmSans(
                      fontSize: 13,
                      color: hasValue ? Colors.white : AppColors.textDisabled,
                      fontWeight: FontWeight.w400,
                      height: multiline ? 1.45 : 1,
                    ),
                    maxLines: multiline ? 4 : 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            if (hasValue)
              Icon(Icons.copy_rounded,
                  size: 14, color: AppColors.textDisabled)
            else
              const Icon(Icons.lock_outline,
                  size: 14, color: AppColors.textDisabled),
          ],
        ),
      ),
    );
  }
}
