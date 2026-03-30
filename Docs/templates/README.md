# LeoBook Premium Email Templates

These templates are designed for the high-end LeoBook SaaS aesthetic: **White Lexend font on a Deep Black background.**

## 🚀 Supabase Dashboard Configuration

Follow these steps to deploy these templates to your project:

1. **Access Supabase Dashboard**: Go to [supabase.com](https://supabase.com/).
2. **Go to Authentication**: From the sidebar, select `Authentication`.
3. **Select Email Templates**: Under the `Configuration` header, click on `Email Templates`.

### Mapping Guide

| Template in Docs | Supabase Entity |
| :--- | :--- |
| `confirm_signup.html` | **Confirm Signup** |
| `invite.html` | **Invite User** |
| `magic_link.html` | **Magic Link / Log In** |
| `change_email.html` | **Change Email Address** |
| `reset_password.html` | **Reset Password** |
| `reauth.html` | **Reauthentication (Token)** |

### Setup Instructions

1. Open the `.html` file from the `docs/templates/` directory.
2. Select all text and **Copy**.
3. In the Supabase Dashboard, select the corresponding template.
4. Paste the HTML into the **Email Body** field.
5. Save your changes.

---

## 💎 Premium Subscription Templates

The following templates are for use with your custom **Super LeoBook** logic (handled via Edge Functions or background workers):

- **Activation**: `subscription_active.html`
- **15-Day Reminder**: `trial_reminder.html`

> [!NOTE]
> All templates use the **Lexend** Google Font. Most modern email clients (Gmail, Outlook Web, Apple Mail) will render this correctly. Older clients will fall back to a clean Sans-Serif font.
