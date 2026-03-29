// phone_utils.dart: Phone number formatting utility.
// Part of LeoBook App — Core Utils

/// Formats a phone number to E.164 standard.
/// Example: +234 + 08012345678 -> +2348012345678
String toE164(String dialCode, String localNumber) {
  // Strip spaces, dashes, parentheses
  var cleanNumber = localNumber.replaceAll(RegExp(r'[\s\-\(\)]'), '');
  
  // Strip leading zero if present
  if (cleanNumber.startsWith('0')) {
    cleanNumber = cleanNumber.substring(1);
  }
  
  final cleanDial = dialCode.trim();
  
  return '$cleanDial$cleanNumber';
}
