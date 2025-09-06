# myApp/admin.py
from __future__ import annotations

import requests
from requests import RequestException

from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.conf import settings
from django.urls import reverse

from .models import Profile, Vision

User = get_user_model()


def _strip_quotes(val: str | None) -> str | None:
    """Handle Windows-style env vars like: RESEND_FROM="PSI <psi@psi.org>"."""
    if not val:
        return val
    v = val.strip()
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        return v[1:-1].strip()
    return v


def _abs_url(request, path: str) -> str:
    """
    Build absolute URL that works behind Railway's proxy.
    Honors SITE_DOMAIN if set; otherwise falls back to request host.
    Forces https if SECURE_SSL_REDIRECT or request is marked secure by proxy header.
    """
    try_https = getattr(settings, "SECURE_SSL_REDIRECT", False)
    scheme = "https" if (request.is_secure() or try_https) else "http"
    domain = getattr(settings, "SITE_DOMAIN", "") or request.get_host() or "localhost:8000"
    return f"{scheme}://{domain}{path}"


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    fk_name = "user"
    extra = 0


class UserAdmin(BaseUserAdmin):
    inlines = [ProfileInline]
    list_display = BaseUserAdmin.list_display + ("onboarded_flag",)
    actions = ["send_password_set_email_resend", "require_onboarding_again"]

    @admin.display(boolean=True, description="Onboarded")
    def onboarded_flag(self, obj):
        prof = getattr(obj, "profile", None)
        return bool(prof and prof.onboarded)

    @admin.action(description="Send password-set email (Resend)")
    def send_password_set_email_resend(self, request, queryset):
        conf = (getattr(settings, "RESEND", {}) or {}).copy()
        api_key   = _strip_quotes(conf.get("API_KEY"))
        from_addr = _strip_quotes(conf.get("FROM") or settings.DEFAULT_FROM_EMAIL)
        reply_to  = _strip_quotes(conf.get("REPLY_TO"))
        base_url  = _strip_quotes(conf.get("BASE_URL") or "https://api.resend.com")

        # Config sanity
        if not api_key:
            self.message_user(request, "Missing RESEND_API_KEY.", level=messages.ERROR)
            return
        if not from_addr:
            self.message_user(request, "Missing RESEND_FROM or DEFAULT_FROM_EMAIL.", level=messages.ERROR)
            return

        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        sent = failed = skipped = 0

        for user in queryset:
            if not getattr(user, "email", None):
                skipped += 1
                continue

            # Build password reset link
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            link = _abs_url(request, reverse("password_reset_confirm", args=[uid, token]))

            subject = "Your PSI Vision account — set your password"
            name = user.get_full_name() or user.username
            html = f"""
              <div style="font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;line-height:1.6">
                <h2 style="color:#1A237E;margin:0 0 12px">Welcome, {name} ✨</h2>
                <p>Your PSI Vision account is ready.</p>
                <p>
                  <a href="{link}" style="background:#1A237E;color:#fff;text-decoration:none;padding:10px 16px;border-radius:10px;display:inline-block">
                    Set your password
                  </a>
                </p>
                <p>If the button doesn’t work, paste this URL into your browser:</p>
                <p style="word-break:break-all"><a href="{link}">{link}</a></p>
                <hr style="border:none;border-top:1px solid #eee;margin:16px 0"/>
                <p style="color:#777;font-size:12px">If you didn’t expect this email, you can ignore it.</p>
              </div>
            """.strip()
            text = f"""Hi {name},

Your PSI Vision account is ready.

Set your password: {link}

If you didn’t expect this email, you can ignore it.
"""

            payload = {
                "from": from_addr,
                "to": [user.email],
                "subject": subject,
                "html": html,
                "text": text,
            }
            if reply_to:
                payload["reply_to"] = reply_to

            try:
                r = requests.post(f"{base_url}/emails", headers=headers, json=payload, timeout=20)
                if r.status_code in (200, 201):
                    sent += 1
                else:
                    failed += 1
                    # Friendlier errors for common cases
                    if r.status_code == 422:
                        msg = "422 Unprocessable Entity (is your From domain/sender verified in Resend?)."
                    elif r.status_code == 429:
                        msg = "429 Too Many Requests (rate limited by Resend). Try again shortly."
                    else:
                        msg = f"{r.status_code} – {r.text[:300]}"
                    self.message_user(request, f"{user.email}: Resend error {msg}", level=messages.ERROR)
            except RequestException as e:
                failed += 1
                self.message_user(request, f"{user.email}: Network error – {e}", level=messages.ERROR)
            except Exception as e:
                failed += 1
                self.message_user(request, f"{user.email}: {e}", level=messages.ERROR)

        # Summary
        if sent:
            self.message_user(request, f"Sent {sent} password-set email(s).", level=messages.SUCCESS)
        if skipped:
            self.message_user(request, f"Skipped {skipped} user(s) without an email.", level=messages.WARNING)
        if failed and not sent:
            self.message_user(request, "Failed to send password-set emails.", level=messages.ERROR)

    @admin.action(description="Require onboarding modal again")
    def require_onboarding_again(self, request, queryset):
        updated = 0
        for user in queryset:
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.onboarded = False
            profile.save(update_fields=["onboarded"])
            updated += 1
        self.message_user(request, f"Marked {updated} user(s) to re-onboard.", level=messages.SUCCESS)


# replace default User admin
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass
admin.site.register(User, UserAdmin)
