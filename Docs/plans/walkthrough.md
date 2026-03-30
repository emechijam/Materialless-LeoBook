# Walkthrough: Password-Based Auth & Biometrics

I have implemented the production-grade authentication flow for LeoBook, transitioning from a basic OTP system to a secure, "Smart Auth" experience with biometric support and mandatory verification.

## Core Changes

### 1. Smart Auth & Password Support
- **Identifier Check**: The `LoginScreen` now uses a "Smart Check" to determine if a user exists.
- **Password Logic**: 
    - Existing users are routed to the new **PasswordEntryScreen** (Glassmorphism UI).
    - New users proceed to the OTP flow for verification and profile setup.
- **Backend Bridge**: `AuthRepository` and `UserCubit` now support `signInWithPassword` using Supabase Auth.

### 2. Biometric Authentication
- **Secure Storage**: Credentials (ID/Password) are encrypted using `flutter_secure_storage` when biometrics are enabled.
- **Convenience Flow**: Successfully implemented `local_auth` integration.
    - **Enrollment**: Users can toggle biometrics during `ProfileSetupScreen`.
    - **Auto-Prompt**: If enabled, the app prompts for biometrics on startup for a seamless experience.

### 3. Smart OTP & SMS Fallback
- **WhatsApp Primary**: OTPs default to WhatsApp (via Twilio/Supabase).
- **30s Rule**: The `OtpVerificationScreen` now features a 30s countdown.
- **SMS Failover**: After 30s, users can trigger an SMS fallback if the WhatsApp message hasn't arrived.

### 4. Mandatory Verification Gating
- **Verified Flag**: Added `phone_verified` and `biometrics_enabled` to `UserModel`.
- **Logic Gate**: A new `UserNeedsVerification` state ensures users cannot access the `MainScreen` without a verified phone number.

## Verification Performed

### [x] Model & Data Integrity
Verified that `UserModel.fromSupabaseUser` correctly parses metadata flags.

### [x] Logic Routing
Confirmed `UserCubit` emits the correct states (`UserNeedsVerification`, `UserBiometricPrompt`, etc.) based on user status and local storage.

### [x] UI & Syntax
- [x] Fixed syntax errors in `ProfileSetupScreen` (missing brackets).
- [x] Restored "Send WhatsApp OTP" button in profile setup.
- [x] Cleaned up unused imports in `LoginScreen`.

> [!IMPORTANT]
> **Manual Action Required**: Since this involves Android/iOS Biometrics, please test on a physical device to verify the `local_auth` prompt and secure storage behavior.

> [!TIP]
> **SMS Fallback**: To test the fallback logic, wait for the 30s timer on the OTP screen to expire. The "Resend via WhatsApp" button will transform into "Send via SMS".
