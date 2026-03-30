# Design Document: LeoBook Password-Based Auth & Biometrics

**Topic:** Password-Based Auth, WhatsApp/SMS Fallbacks, and Biometric Integration
**Date:** 2026-03-29
**Status:** Approved (Brainstorming Phase Complete)

## 1. Goal
Implement a production-grade authentication flow that supports password-based sign-ins, maintains the existing three-button UI, handles new user registration via WhatsApp/SMS OTP, and introduces automatic (but dismissible) biometric authentication.

## 2. Requirements & Constraints
- **UI Persistence:** The three main buttons (Google, Email, Phone) on the Login Screen must remain visually unchanged.
- **Smart Logic:**
    - **Existing Users:** Sign in via Password (OTP is skipped).
    - **New Users:** Sign up via Phone/WhatsApp OTP -> Move to Profile Setup.
- **Verification Gate:** Phone number verification is **mandatory** for all accounts (including Google/Email signups) before they access the main app features.
- **OTP Delivery:** WhatsApp is the primary channel. A 30-second "Resend via SMS" fallback is required.
- **Security:** Email notification sent to the user on every successful login, detailing the device model and IP address.
- **Biometrics:** Automatic trigger on app load if previously enabled, but with a clear "Dismiss" option to use the standard login buttons.

## 3. Architecture & Components

### A. Data Layer (AuthRepository)
- **`signInWithPassword(identifier, password)`**: Main entry point for existing users.
- **`sendPhoneOtp(phone, channel)`**: Supports `whatsapp` first, then `sms` on fallback.
- **`logUserSession(deviceInfo)`**: Captures `device_info_plus` details and triggers notification.
- **`hasBiometricsEnabled()`**: Check shared preferences for opt-in state.

### B. Logic Layer (UserCubit)
- **`checkUserStatus(identifier)`**: Internal helper to decide between Password vs. OTP flow based on `signInWithPassword` response.
- **`UserNeedsVerification` state**: A required middleware state that forces the user to the `OtpVerificationScreen` if their `phone_verified` attribute is false.
- **`UserBiometricPrompt` state**: Emitted on app load if biometrics are enabled, triggering the native UI.

### C. UI Layer
- **`LoginScreen`**: Unchanged layout, but "Continue with Phone/Email" buttons now trigger "Smart Check" logic.
- **`PasswordEntryScreen` (New)**: A dedicated, glassmorphism-style screen that appears for recognized users.
- **`OtpVerificationScreen` (Updated)**: Added a 30s countdown timer that switches the resend button from "Resend WhatsApp" to "Send via SMS".
- **`ProfileSetupScreen` (Updated)**: Now enforces creating a password and verifies phone number for Google/Email users.

## 4. Biometric Logic
- **Hardware Check:** Uses `local_auth` to verify device capabilities.
- **Secure Vault:** Uses `flutter_secure_storage` to save credentials (phone/password) locally.
- **Auto-Invocation:** `UserCubit` checks for a stored vault on `AppStarted`. If found, it emits a state that triggers the biometric prompt immediately over the `LoginScreen`.

## 5. Verification Plan
- **Unit Tests:** Verify `UserCubit` transitions for new vs. existing users.
- **Manual Verification:** 
    - Test registration flow (WhatsApp -> SMS -> Profile Setup).
    - Test login flow (Email notification with correct IP/Device info).
    - Test Biometric auto-trigger and "Dismiss" behavior.
