"""Verificación de correo con código de 6 dígitos.

Flujo: el administrador crea el usuario (inactivo) → se envía un código al correo →
el dueño del correo envía el código y su contraseña → la cuenta queda activa.
"""

import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from rest_framework.exceptions import ValidationError

from apps.shop.services import get_settings

from .models import EmailVerification, User

INVALID_CODE = "Código inválido o vencido. Solicita uno nuevo."


def _hash_code(user_id: int, code: str) -> str:
    return salted_hmac("invexa.email-verification", f"{user_id}:{code}").hexdigest()


def _active_codes(user: User):
    return EmailVerification.objects.filter(user=user, used_at__isnull=True)


def send_password_changed_notice(user: User) -> None:
    """Avisa por correo que la contraseña cambió, con cómo recuperar la cuenta si no fue el dueño."""
    context = {
        "user": user,
        "business_name": get_settings().name,
        "changed_at": timezone.localtime(timezone.now()),
        "reset_url": f"{settings.INVEXA_APP_URL}/recuperar",
    }
    subject = "Cambiaste tu contraseña de Invexa"
    text = render_to_string("users/email/password_changed.txt", context)
    html = render_to_string("users/email/password_changed.html", context)
    transaction.on_commit(
        lambda: send_mail(subject, text, None, [user.email], html_message=html, fail_silently=False)
    )


def send_verification_code(user: User) -> None:
    """Genera un código nuevo, invalida los anteriores y lo envía por correo tras el commit."""
    now = timezone.now()
    code = f"{secrets.randbelow(1_000_000):06d}"
    minutes = settings.INVEXA_VERIFICATION_CODE_MINUTES

    with transaction.atomic():
        _active_codes(user).update(used_at=now)
        EmailVerification.objects.create(
            user=user,
            code_hash=_hash_code(user.pk, code),
            expires_at=now + timedelta(minutes=minutes),
        )

    context = {
        "user": user,
        "code": code,
        "minutes": minutes,
        "business_name": get_settings().name,
    }
    subject = f"{code} es tu código de verificación de Invexa"
    text = render_to_string("users/email/verification_code.txt", context)
    html = render_to_string("users/email/verification_code.html", context)

    transaction.on_commit(
        lambda: send_mail(subject, text, None, [user.email], html_message=html, fail_silently=False)
    )


def resend_verification_code(email: str) -> None:
    """Reenvía el código. No revela si el correo existe (respuesta siempre igual)."""
    user = User.objects.filter(email__iexact=email, email_verified_at__isnull=True).first()
    if user is None:
        return
    last = user.email_verifications.first()
    wait = timedelta(seconds=settings.INVEXA_VERIFICATION_RESEND_SECONDS)
    if last and timezone.now() - last.created_at < wait:
        # Dentro del tiempo de espera no se envía nada, pero la respuesta es la misma
        # para no revelar qué correos existen.
        return
    send_verification_code(user)


def _consume_code(user: User, code: str) -> bool:
    """Marca el código como usado si es correcto y vigente; cuenta los intentos fallidos."""
    verified = False
    with transaction.atomic():
        verification = _active_codes(user).select_for_update().first()
        now = timezone.now()
        if verification is not None and verification.expires_at >= now:
            if constant_time_compare(verification.code_hash, _hash_code(user.pk, code)):
                verification.used_at = now
                verification.save(update_fields=["used_at"])
                verified = True
            else:
                verification.attempts += 1
                if verification.attempts >= settings.INVEXA_VERIFICATION_MAX_ATTEMPTS:
                    verification.used_at = now
                verification.save(update_fields=["attempts", "used_at"])
    return verified


def verify_email(*, email: str, code: str, password: str) -> User:
    """Valida el código, define la contraseña y activa la cuenta."""
    user = User.objects.filter(email__iexact=email, email_verified_at__isnull=True).first()
    if user is None or not _consume_code(user, code):
        raise ValidationError({"code": INVALID_CODE})
    now = timezone.now()
    user.set_password(password)
    user.is_active = True
    user.email_verified_at = now
    user.save(update_fields=["password", "is_active", "email_verified_at"])
    return user


def request_password_reset(email: str) -> None:
    """Envía un código para recuperar la contraseña. Responde igual exista o no el correo."""
    user = User.objects.filter(email__iexact=email, is_active=True, email_verified_at__isnull=False).first()
    if user is None:
        return
    last = user.email_verifications.first()
    wait = timedelta(seconds=settings.INVEXA_VERIFICATION_RESEND_SECONDS)
    if last and timezone.now() - last.created_at < wait:
        return

    now = timezone.now()
    code = f"{secrets.randbelow(1_000_000):06d}"
    minutes = settings.INVEXA_VERIFICATION_CODE_MINUTES
    with transaction.atomic():
        _active_codes(user).update(used_at=now)
        EmailVerification.objects.create(
            user=user,
            code_hash=_hash_code(user.pk, code),
            expires_at=now + timedelta(minutes=minutes),
        )
    context = {
        "user": user,
        "code": code,
        "minutes": minutes,
        "business_name": get_settings().name,
    }
    subject = f"{code} es tu código para recuperar tu contraseña de Invexa"
    text = render_to_string("users/email/password_reset_code.txt", context)
    html = render_to_string("users/email/password_reset_code.html", context)
    transaction.on_commit(
        lambda: send_mail(subject, text, None, [user.email], html_message=html, fail_silently=False)
    )


def reset_password(*, email: str, code: str, password: str) -> User:
    """Cambia la contraseña con el código recibido por correo."""
    user = User.objects.filter(email__iexact=email, is_active=True, email_verified_at__isnull=False).first()
    if user is None or not _consume_code(user, code):
        raise ValidationError({"code": INVALID_CODE})
    user.set_password(password)
    user.save(update_fields=["password"])
    return user
