"""
farmasyst_north/email_service.py

Transactional email delivery for FarmAsyst North.
Uses Django's send_mail() — configure EMAIL_* settings in settings.py.
Compatible with SendGrid, Mailgun, and standard SMTP (Gmail, etc.).

All functions are fire-and-forget: exceptions are caught and logged so
an email failure never crashes a business transaction.
"""
import logging
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)

FROM = getattr(settings, 'DEFAULT_FROM_EMAIL', 'FarmAsyst North <noreply@farmasystnorth.com>')


def _send(to: str, subject: str, body_text: str, body_html: str = None):
    try:
        send_mail(
            subject=subject,
            message=body_text,
            from_email=FROM,
            recipient_list=[to],
            html_message=body_html,
            fail_silently=False,
        )
        logger.info('Email sent to %s: %s', to, subject)
    except Exception as exc:
        logger.error('Email failed to %s (%s): %s', to, subject, exc)


def _html(title: str, body_html: str) -> str:
    """Minimal branded HTML wrapper."""
    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{title}</title></head>
<body style="font-family:Arial,sans-serif;background:#f5f5f0;padding:0;margin:0;">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center" style="padding:32px 16px;">
      <table width="540" style="background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.08);">
        <tr>
          <td style="background:#2D4A1E;padding:24px 32px;">
            <span style="color:#E8A020;font-size:20px;font-weight:700;font-family:Georgia,serif;">FarmAsyst</span>
            <span style="color:#fff;font-size:13px;letter-spacing:0.2em;margin-left:6px;">NORTH</span>
          </td>
        </tr>
        <tr><td style="padding:32px;">{body_html}</td></tr>
        <tr>
          <td style="background:#f5f5f0;padding:16px 32px;font-size:12px;color:#888;text-align:center;">
            FarmAsyst North · AgriFinTech Platform · Northern Ghana<br>
            If you did not request this email, you can safely ignore it.
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


# ── OTP Verification ──────────────────────────────────────────────────────────

def send_email_otp(email: str, name: str, otp: str):
    subject = 'Verify your FarmAsyst North email address'
    text = (
        f'Hi {name},\n\n'
        f'Your FarmAsyst North email verification code is: {otp}\n\n'
        f'This code expires in 10 minutes. Do not share it with anyone.\n\n'
        f'— FarmAsyst North Team'
    )
    html = _html(subject, f"""
        <h2 style="color:#2D4A1E;margin:0 0 16px;">Verify your email</h2>
        <p style="color:#444;margin:0 0 24px;">Hi <strong>{name}</strong>,</p>
        <p style="color:#444;margin:0 0 24px;">
            Enter the code below to verify your FarmAsyst North account:
        </p>
        <div style="background:#f5f5f0;border-radius:8px;padding:24px;text-align:center;margin:0 0 24px;">
            <span style="font-size:36px;font-weight:700;letter-spacing:0.18em;color:#2D4A1E;">{otp}</span>
        </div>
        <p style="color:#888;font-size:13px;margin:0;">
            This code expires in <strong>10 minutes</strong>. Do not share it with anyone.
        </p>
    """)
    _send(email, subject, text, html)


# ── Account notifications ─────────────────────────────────────────────────────

def send_welcome_email(email: str, name: str, role: str):
    subject = f'Welcome to FarmAsyst North, {name}!'
    role_label = role.replace('_', ' ').title()
    text = (
        f'Hi {name},\n\nWelcome to FarmAsyst North! Your {role_label} account is ready.\n\n'
        f'Log in at https://farmasyst-north-frontend.onrender.com\n\n'
        f'— FarmAsyst North Team'
    )
    html = _html(subject, f"""
        <h2 style="color:#2D4A1E;margin:0 0 16px;">Welcome to FarmAsyst North 🎉</h2>
        <p style="color:#444;margin:0 0 16px;">Hi <strong>{name}</strong>,</p>
        <p style="color:#444;margin:0 0 16px;">
            Your <strong>{role_label}</strong> account has been verified and is ready to use.
        </p>
        <p style="color:#444;margin:0 0 24px;">
            You can now log in and access your portal.
        </p>
        <a href="https://farmasyst-north-frontend.onrender.com"
           style="background:#2D4A1E;color:#fff;text-decoration:none;padding:12px 24px;border-radius:8px;font-weight:600;display:inline-block;">
            Go to my portal →
        </a>
    """)
    _send(email, subject, text, html)


def send_account_pending_email(email: str, name: str, role: str):
    subject = 'Your FarmAsyst North account is pending approval'
    role_label = role.replace('_', ' ').title()
    text = (
        f'Hi {name},\n\nYour {role_label} account has been created and is awaiting admin approval.\n'
        f'You will be notified by email once it is activated.\n\n'
        f'— FarmAsyst North Team'
    )
    html = _html(subject, f"""
        <h2 style="color:#2D4A1E;margin:0 0 16px;">Account pending approval</h2>
        <p style="color:#444;margin:0 0 16px;">Hi <strong>{name}</strong>,</p>
        <p style="color:#444;margin:0 0 16px;">
            Your <strong>{role_label}</strong> account has been created and is pending review
            by a FarmAsyst North administrator.
        </p>
        <p style="color:#888;font-size:13px;margin:0;">
            You will receive an email and SMS notification once your account is approved.
        </p>
    """)
    _send(email, subject, text, html)


# ── Credit lifecycle emails ───────────────────────────────────────────────────

def send_credit_status_email(email: str, name: str, ref: str, status: str, detail: str = ''):
    labels = {
        'submitted':    ('Application Received', '📝 Your application has been received and is under review.'),
        'under_review': ('Application Under Review', '🔍 Your application is currently being reviewed.'),
        'approved':     ('Application Approved! ✅', '🎉 Great news — your credit application has been approved.'),
        'rejected':     ('Application Decision', '❌ Your application was not approved at this time.'),
        'matched':      ('Investor Matched! 🤝', '✅ Your application has been matched with an investor.'),
        'agreement':    ('Contract Ready to Sign 📄', '📄 Your investment agreement is ready for your review and signature.'),
        'disbursed':    ('Funds Disbursed! 🏦', '💰 Your credit funds have been disbursed.'),
    }
    title, headline = labels.get(status, ('Application Update', 'Your application has been updated.'))
    subject = f'FarmAsyst North: {title} — {ref}'
    text = f'Hi {name},\n\n{headline}\nReference: {ref}\n{detail}\n\n— FarmAsyst North'
    detail_block = f'<p style="color:#444;margin:0 0 16px;">{detail}</p>' if detail else ''
    html = _html(subject, f"""
        <h2 style="color:#2D4A1E;margin:0 0 16px;">{title}</h2>
        <p style="color:#444;margin:0 0 16px;">Hi <strong>{name}</strong>,</p>
        <p style="color:#444;margin:0 0 16px;">{headline}</p>
        <div style="background:#f5f5f0;border-radius:8px;padding:16px;margin:0 0 16px;">
            <strong>Reference:</strong> {ref}
        </div>
        {detail_block}
        <a href="https://farmasyst-north-frontend.onrender.com"
           style="background:#2D4A1E;color:#fff;text-decoration:none;padding:10px 20px;border-radius:8px;font-weight:600;display:inline-block;">
            View my application →
        </a>
    """)
    _send(email, subject, text, html)


def send_repayment_confirmation_email(email: str, name: str, ref: str, amount: float, method: str):
    subject = f'FarmAsyst North: Repayment Confirmed — {ref}'
    text = f'Hi {name},\n\nYour repayment of GHS {amount:.2f} via {method} (ref #{ref}) has been confirmed. Thank you!\n\n— FarmAsyst North'
    html = _html(subject, f"""
        <h2 style="color:#2D4A1E;margin:0 0 16px;">Repayment Confirmed 💰</h2>
        <p style="color:#444;margin:0 0 16px;">Hi <strong>{name}</strong>,</p>
        <p style="color:#444;margin:0 0 16px;">
            Your repayment has been received and confirmed.
        </p>
        <div style="background:#f0fdf4;border-radius:8px;padding:16px;margin:0 0 16px;border:1px solid #bbf7d0;">
            <strong>Amount:</strong> GHS {amount:.2f}<br>
            <strong>Method:</strong> {method}<br>
            <strong>Reference:</strong> {ref}
        </div>
        <a href="https://farmasyst-north-frontend.onrender.com"
           style="background:#2D4A1E;color:#fff;text-decoration:none;padding:10px 20px;border-radius:8px;font-weight:600;display:inline-block;">
            View my repayments →
        </a>
    """)
    _send(email, subject, text, html)


def send_order_confirmation_email(email: str, name: str, order_ref: str, amount: float):
    subject = f'FarmAsyst North: Order Confirmed — #{order_ref}'
    text = f'Hi {name},\n\nYour order #{order_ref} of GHS {amount:.2f} has been placed.\n\n— FarmAsyst North'
    html = _html(subject, f"""
        <h2 style="color:#2D4A1E;margin:0 0 16px;">Order Confirmed 🛒</h2>
        <p style="color:#444;margin:0 0 16px;">Hi <strong>{name}</strong>,</p>
        <p style="color:#444;margin:0 0 16px;">
            Your order has been placed and is being processed.
        </p>
        <div style="background:#f5f5f0;border-radius:8px;padding:16px;margin:0 0 16px;">
            <strong>Order:</strong> #{order_ref}<br>
            <strong>Total:</strong> GHS {amount:.2f}
        </div>
        <a href="https://farmasyst-north-frontend.onrender.com"
           style="background:#2D4A1E;color:#fff;text-decoration:none;padding:10px 20px;border-radius:8px;font-weight:600;display:inline-block;">
            Track my order →
        </a>
    """)
    _send(email, subject, text, html)
