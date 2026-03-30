# LeoBook v9.5.5: Professional SMTP & Security Alerts Configuration

This guide provides the exact values and steps needed to enable production-grade emails for LeoBook using **Resend**.

## 🚀 1. Enable Custom SMTP (Supabase Dashboard)

Go to **Authentication** -> **SMTP Settings** and fill in the following values:

| Field | Value |
| :--- | :--- |
| **Sender Email Address** | `onboarding@resend.dev` |
| **Sender Name** | `Resend Testing` |
| **Host** | `smtp.resend.com` |
| **Port Number** | `465` (SSL) or `587` (TLS) |
| **Minimum Interval** | `60` seconds |
| **Username** | `resend` |
| **Password** | (Paste your **Resend API Key** here) |

> [!IMPORTANT]
> Ensure you have **verified your domain** in the Resend dashboard before enabling SMTP.

## 🔒 2. Security Alerts (Email Templates)

The newly expanded security alerts (v9.5.5) should be configured in the **Auth -> Email Templates** section. 

The following 7 templates have been designed with the "LOBOOK Black Elite" aesthetic:
- ✅ [Password Changed](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/docs/templates/password_changed.html)
- ✅ [Email Address Changed](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/docs/templates/email_changed_notify.html)
- ✅ [Phone Number Changed](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/docs/templates/phone_changed.html)
- ✅ [Identity Linked](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/docs/templates/identity_linked.html)
- ✅ [Identity Unlinked](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/docs/templates/identity_unlinked.html)
- ✅ [MFA Method Added](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/docs/templates/mfa_added.html)
- ✅ [MFA Method Removed](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/docs/templates/mfa_removed.html)

---

## ⚡ FIX: Supabase CLI & Deployment

Since `npm install -g supabase` is not supported, use the **NPX** version for all commands.

### 1. Initialize Supabase (One-time)
If you haven't yet, initialize the project from the root:
```powershell
npx supabase init
```

### 2. Login & Link (Required for Deployment)
```powershell
npx supabase login
npx supabase link --project-ref jefoqzewyvscdqcpnjxu
```

### 3. Deploy Edge Function
The function is located at `supabase/functions/trigger-email/index.ts`.
```powershell
npx supabase functions deploy trigger-email
npx supabase secrets set RESEND_API_KEY=your_key_here
```
