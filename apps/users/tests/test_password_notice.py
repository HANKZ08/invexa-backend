from django.core import mail
from django.urls import reverse

from conftest import PASSWORD

NEW_PASSWORD = "Otra-Clave-987"


def test_changing_the_password_sends_a_notice_to_the_user(
    client_for, cashier, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        response = client_for(cashier).post(
            reverse("change_password"),
            {"current_password": PASSWORD, "new_password": NEW_PASSWORD},
        )
    assert response.status_code == 204
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == [cashier.email]
    assert "contraseña" in message.subject
    assert "NO fuiste tú" in message.body
    assert message.alternatives  # versión HTML incluida


def test_a_failed_change_sends_no_notice(client_for, cashier, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        response = client_for(cashier).post(
            reverse("change_password"),
            {"current_password": "mal", "new_password": NEW_PASSWORD},
        )
    assert response.status_code == 400
    assert mail.outbox == []
