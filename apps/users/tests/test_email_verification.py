import re
from datetime import timedelta

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from apps.users.models import EmailVerification, User

pytestmark = pytest.mark.django_db

NEW_PASSWORD = "Nueva-Clave-2026"


def last_code() -> str:
    """Extrae el código de 6 dígitos del último correo enviado."""
    return re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)


@pytest.fixture
def pending_user(client_for, admin_user, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        response = client_for(admin_user).post(
            reverse("user-list"),
            {"username": "nueva", "email": "nueva@test.local", "role": "cashier", "first_name": "Ana"},
        )
    assert response.status_code == 201, response.data
    return User.objects.get(username="nueva")


def verify(api_client, code, email="nueva@test.local", password=NEW_PASSWORD):
    return api_client.post(
        reverse("verify_email"), {"email": email, "code": code, "password": password}, format="json"
    )


def test_creating_user_sends_code_and_leaves_account_inactive(pending_user):
    assert pending_user.is_active is False
    assert pending_user.email_verified_at is None
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == ["nueva@test.local"]
    assert last_code() in message.subject
    assert message.alternatives  # versión HTML


def test_code_is_stored_hashed(pending_user):
    code = last_code()
    verification = EmailVerification.objects.get(user=pending_user)
    assert code not in verification.code_hash


def test_inactive_user_cannot_login(api_client, pending_user):
    response = api_client.post(reverse("token_obtain_pair"), {"username": "nueva", "password": "x"})
    assert response.status_code == 401


def test_valid_code_activates_account_and_sets_password(api_client, pending_user):
    response = verify(api_client, last_code())
    assert response.status_code == 200, response.data
    pending_user.refresh_from_db()
    assert pending_user.is_active is True
    assert pending_user.email_verified_at is not None
    assert pending_user.check_password(NEW_PASSWORD)

    login = api_client.post(reverse("token_obtain_pair"), {"username": "nueva", "password": NEW_PASSWORD})
    assert login.status_code == 200


def test_code_cannot_be_reused(api_client, pending_user):
    code = last_code()
    assert verify(api_client, code).status_code == 200
    assert verify(api_client, code).status_code == 400


def test_wrong_code_is_rejected_and_counted(api_client, pending_user):
    code = last_code()
    wrong = "000000" if code != "000000" else "111111"
    assert verify(api_client, wrong).status_code == 400
    assert EmailVerification.objects.get(user=pending_user).attempts == 1


def test_code_is_invalidated_after_max_attempts(api_client, pending_user, settings):
    code = last_code()
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(settings.INVEXA_VERIFICATION_MAX_ATTEMPTS):
        verify(api_client, wrong)
    # Incluso el código correcto deja de servir
    assert verify(api_client, code).status_code == 400


def test_expired_code_is_rejected(api_client, pending_user):
    EmailVerification.objects.filter(user=pending_user).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )
    assert verify(api_client, last_code()).status_code == 400


def test_weak_password_is_rejected(api_client, pending_user):
    response = verify(api_client, last_code(), password="123")
    assert response.status_code == 400
    assert "password" in response.data


def test_resend_invalidates_previous_code(api_client, pending_user, django_capture_on_commit_callbacks):
    old_code = last_code()
    EmailVerification.objects.update(created_at=timezone.now() - timedelta(minutes=2))
    with django_capture_on_commit_callbacks(execute=True):
        response = api_client.post(reverse("resend_code"), {"email": "nueva@test.local"})
    assert response.status_code == 200
    new_code = last_code()
    if new_code != old_code:
        assert verify(api_client, old_code).status_code == 400
    assert verify(api_client, new_code).status_code == 200


def test_resend_has_cooldown(api_client, pending_user, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        response = api_client.post(reverse("resend_code"), {"email": "nueva@test.local"})
    # Misma respuesta que un correo desconocido, pero no se envía otro código
    assert response.status_code == 200
    assert len(mail.outbox) == 1


def test_resend_does_not_reveal_unknown_emails(api_client):
    response = api_client.post(reverse("resend_code"), {"email": "nadie@test.local"})
    assert response.status_code == 200
    assert len(mail.outbox) == 0


def test_admin_cannot_activate_unverified_user(client_for, admin_user, pending_user):
    response = client_for(admin_user).patch(
        reverse("user-detail", args=[pending_user.pk]), {"is_active": True}
    )
    assert response.status_code == 400


def test_admin_cannot_set_password_on_create(client_for, admin_user):
    response = client_for(admin_user).post(
        reverse("user-list"),
        {"username": "x", "email": "x@test.local", "role": "cashier", "password": "Segura-12345"},
    )
    assert response.status_code == 400


def test_changing_email_requires_new_verification(
    client_for, admin_user, cashier, django_capture_on_commit_callbacks
):
    cashier.email_verified_at = timezone.now()
    cashier.save()
    with django_capture_on_commit_callbacks(execute=True):
        response = client_for(admin_user).patch(
            reverse("user-detail", args=[cashier.pk]), {"email": "nuevo-correo@test.local"}
        )
    assert response.status_code == 200
    cashier.refresh_from_db()
    assert cashier.is_active is False
    assert cashier.email_verified_at is None
    assert mail.outbox[-1].to == ["nuevo-correo@test.local"]
