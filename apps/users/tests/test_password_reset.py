import re

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from apps.users.models import User

pytestmark = pytest.mark.django_db

NEW_PASSWORD = "Nueva-Clave-2026"


@pytest.fixture
def verified_cashier(cashier):
    cashier.email_verified_at = timezone.now()
    cashier.save(update_fields=["email_verified_at"])
    return cashier


def code_from_outbox() -> str:
    body = mail.outbox[-1].body
    return re.search(r"\b(\d{6})\b", body).group(1)


def test_request_sends_a_code_to_a_verified_active_user(
    api_client, verified_cashier, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        response = api_client.post(
            reverse("password_reset"), {"email": verified_cashier.email}, format="json"
        )
    assert response.status_code == 200
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [verified_cashier.email]
    assert "recuperar" in mail.outbox[0].subject.lower()


def test_request_for_unknown_email_sends_nothing_but_answers_the_same(
    api_client, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        response = api_client.post(reverse("password_reset"), {"email": "nadie@test.local"}, format="json")
    assert response.status_code == 200
    assert mail.outbox == []


def test_request_for_unverified_account_sends_nothing(
    api_client, cashier, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        api_client.post(reverse("password_reset"), {"email": cashier.email}, format="json")
    assert mail.outbox == []


def test_the_code_changes_the_password(api_client, verified_cashier, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        api_client.post(reverse("password_reset"), {"email": verified_cashier.email}, format="json")
    code = code_from_outbox()

    response = api_client.post(
        reverse("password_reset_confirm"),
        {"email": verified_cashier.email, "code": code, "password": NEW_PASSWORD},
        format="json",
    )
    assert response.status_code == 204
    verified_cashier.refresh_from_db()
    assert verified_cashier.check_password(NEW_PASSWORD)


def test_a_wrong_code_is_rejected(api_client, verified_cashier, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        api_client.post(reverse("password_reset"), {"email": verified_cashier.email}, format="json")
    wrong = "000000" if code_from_outbox() != "000000" else "111111"
    response = api_client.post(
        reverse("password_reset_confirm"),
        {"email": verified_cashier.email, "code": wrong, "password": NEW_PASSWORD},
        format="json",
    )
    assert response.status_code == 400
    verified_cashier.refresh_from_db()
    assert not verified_cashier.check_password(NEW_PASSWORD)


def test_a_code_works_only_once(api_client, verified_cashier, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        api_client.post(reverse("password_reset"), {"email": verified_cashier.email}, format="json")
    code = code_from_outbox()
    payload = {"email": verified_cashier.email, "code": code, "password": NEW_PASSWORD}
    assert api_client.post(reverse("password_reset_confirm"), payload, format="json").status_code == 204
    assert api_client.post(reverse("password_reset_confirm"), payload, format="json").status_code == 400
    assert User.objects.get(pk=verified_cashier.pk).check_password(NEW_PASSWORD)
