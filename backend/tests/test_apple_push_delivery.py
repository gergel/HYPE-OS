"""Isolated SQLite DB + mocked APNs; never sends external notifications."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import json
import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.core.database import Base
from app.models.employee import Employee, EmployeeType
from app.models.notification import Notification
from app.models.push import PushDevice, PushDelivery, NotificationPreference
from app.services.notifications import create_notification
from app.services.push_delivery import process_one
from app.services.apple_push import ApplePush, PushConfig, payload


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[Employee.__table__, Notification.__table__, PushDevice.__table__, PushDelivery.__table__, NotificationPreference.__table__])
    with Session(engine) as session:
        session.add_all([Employee(id=1, full_name="Recipient", tipus=EmployeeType.BELSOS, is_active=True),
                         Employee(id=2, full_name="Other account", tipus=EmployeeType.BELSOS, is_active=True)])
        session.add(PushDevice(employee_id=1, token="a" * 64, environment="sandbox", expires_at=datetime.now(timezone.utc) + timedelta(days=1)))
        session.commit()
        yield session
    engine.dispose()


def notify(db):
    create_notification(db, employee_id=1, kind="mention", message="Test mention", link="/utomunka/23", actor_id=2)
    db.commit()


class FakeTransport:
    def __init__(self, result="sent"):
        self.result = result
        self.calls = 0
    def send(self, device, notification):
        self.calls += 1
        return self.result


def test_rollback_never_creates_delivery(db):
    create_notification(db, employee_id=1, kind="assignment", message="Rolled back", link="/feladatok/1", actor_id=2)
    db.rollback()
    assert list(db.scalars(select(Notification))) == []
    assert list(db.scalars(select(PushDelivery))) == []


def test_self_action_and_old_notifications_not_pushed(db):
    create_notification(db, employee_id=1, kind="mention", message="Self", link="/", actor_id=1)
    db.add(Notification(employee_id=1, kind="mention", message="Historical", link="/"))
    db.commit()
    assert list(db.scalars(select(PushDelivery))) == []


def test_success_once_per_device(db):
    notify(db)
    transport = FakeTransport()
    assert process_one(db, transport)
    assert not process_one(db, transport)
    assert transport.calls == 1
    assert db.scalar(select(PushDelivery)).result == "sent"


def test_retry_and_backoff(db):
    notify(db)
    transport = FakeTransport("retry")
    now = datetime.now(timezone.utc)
    assert process_one(db, transport, now)
    delivery = db.scalar(select(PushDelivery))
    assert delivery.completed_at is None and delivery.attempts == 1
    assert not process_one(db, transport, now + timedelta(seconds=5))
    transport.result = "sent"
    assert process_one(db, transport, now + timedelta(seconds=31))
    assert delivery.completed_at is not None and transport.calls == 2


@pytest.mark.parametrize("reason", ["reassigned", "expired", "inactive", "read", "old"])
def test_no_delivery_to_ineligible_recipient(db, reason):
    notify(db)
    device = db.scalar(select(PushDevice))
    notification = db.scalar(select(Notification))
    if reason == "reassigned": device.employee_id = 2
    if reason == "expired": device.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    if reason == "inactive": db.get(Employee, 1).is_active = False
    if reason == "read": notification.is_read = True
    if reason == "old": notification.created_at = datetime.now(timezone.utc) - timedelta(days=2)
    db.commit()
    transport = FakeTransport()
    assert process_one(db, transport)
    assert transport.calls == 0
    assert db.scalar(select(PushDelivery)).result == "skipped"


def test_invalid_device_is_disabled(db):
    notify(db)
    assert process_one(db, FakeTransport("invalid_device"))
    assert db.scalar(select(PushDelivery)).result == "invalid_device"
    create_notification(db, employee_id=1, kind="assignment", message="Next", link="/feladatok/2")
    db.commit()
    assert len(list(db.scalars(select(PushDelivery)))) == 1


@pytest.mark.parametrize("environment,host", [("sandbox", "api.sandbox.push.apple.com"), ("production", "api.push.apple.com")])
def test_apns_headers_and_payload(environment, host):
    private_key = ec.generate_private_key(ec.SECP256R1()).private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    received = []
    def handle(request):
        received.append(request)
        return httpx.Response(200)
    transport = ApplePush(PushConfig("TEST_KEY", "TEST_TEAM", private_key, "com.hypeclient.apple.dev"), httpx.Client(transport=httpx.MockTransport(handle)))
    device = SimpleNamespace(id=4, token="a" * 64, environment=environment)
    notification = SimpleNamespace(id=12, employee_id=1, kind="call_sheet", message="Új diszpó", link="/diszpoim?project_id=3", created_at=datetime.now(timezone.utc))
    assert transport.send(device, notification) == "sent"
    request = received[0]
    assert request.url.host == host
    assert request.headers["apns-topic"] == "com.hypeclient.apple.dev"
    assert request.headers["apns-push-type"] == "alert"
    body = json.loads(request.content)
    assert body["employee_id"] == 1 and body["notification_id"] == 12
    assert body["aps"]["alert"]["title"] == "Új diszpód érkezett"
    assert body["link"] == "/diszpoim?project_id=3"
    assert len(payload(notification)) < 4096
    transport.client.close()


@pytest.mark.parametrize("code,reason,outcome", [(410, "Unregistered", "invalid_device"), (400, "BadDeviceToken", "invalid_device"), (429, "TooManyRequests", "retry"), (503, "ServiceUnavailable", "retry"), (413, "PayloadTooLarge", "invalid_payload")])
def test_apns_response_classification(code, reason, outcome):
    transport = ApplePush(PushConfig("k", "t", "key", "topic"), httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(code, json={"reason": reason}))))
    transport._jwt = "fake"; transport._issued = int(datetime.now().timestamp())
    assert transport.send(SimpleNamespace(id=1, token="a" * 64, environment="sandbox"), SimpleNamespace(id=1, employee_id=1, kind="mention", message="test", link="/", created_at=datetime.now(timezone.utc))) == outcome
    transport.client.close()


def test_two_devices_and_expired_registration(db):
    db.add_all([PushDevice(employee_id=1, token="b" * 64, environment="production", expires_at=datetime.now(timezone.utc) + timedelta(days=1)),
                PushDevice(employee_id=1, token="c" * 64, environment="sandbox", expires_at=datetime.now(timezone.utc) - timedelta(days=1))])
    db.commit()
    notify(db)
    assert len(list(db.scalars(select(PushDelivery)))) == 2
    transport = FakeTransport()
    while process_one(db, transport): pass
    assert transport.calls == 2


def test_registration_reassigns_and_delete_checks_owner(db):
    import importlib.util
    from pathlib import Path
    from app.core.security import create_access_token
    spec = importlib.util.spec_from_file_location("push_routes_for_test", Path(__file__).parents[1] / "app/api/routes/notifications.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    token = "a" * 64
    module.register_device(module.DeviceRegistration(token=token, environment="sandbox"), db, db.get(Employee, 2), create_access_token("2", "operator"))
    assert db.scalar(select(PushDevice)).employee_id == 2
    module.unregister_device(module.DeviceToken(token=token), db, db.get(Employee, 1))
    assert db.scalar(select(PushDevice)) is not None
    module.unregister_device(module.DeviceToken(token=token), db, db.get(Employee, 2))
    assert db.scalar(select(PushDevice)) is None


def test_invalid_device_token_rejected():
    import importlib.util
    from pathlib import Path
    from pydantic import ValidationError
    spec = importlib.util.spec_from_file_location("push_schema_test", Path(__file__).parents[1] / "app/api/routes/notifications.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with pytest.raises(ValidationError): module.DeviceRegistration(token="../../bad", environment="sandbox")
    with pytest.raises(ValidationError): module.DeviceRegistration(token="a" * 64, environment="unknown")


def test_device_endpoints_require_login():
    import importlib.util
    from pathlib import Path
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    spec = importlib.util.spec_from_file_location("push_auth_test", Path(__file__).parents[1] / "app/api/routes/notifications.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    app = FastAPI()
    app.include_router(module.router)
    # No database access or real token is involved in an unauthenticated call.
    app.dependency_overrides[module.get_db] = lambda: None
    client = TestClient(app)
    assert client.put("/notifications/devices", json={"token": "a" * 64, "environment": "sandbox"}).status_code == 401
    assert client.request("DELETE", "/notifications/devices", json={"token": "a" * 64}).status_code == 401


def test_exception_is_retried_without_losing_outbox(db):
    notify(db)
    class BrokenTransport:
        def send(self, device, notification):
            raise httpx.ConnectError("offline")
    assert process_one(db, BrokenTransport())
    row = db.scalar(select(PushDelivery))
    assert row.result == "retry" and row.completed_at is None and row.attempts == 1


def test_other_inbox_events_do_not_interrupt_phone(db):
    create_notification(db, employee_id=1, kind="future_unknown_event", message="Unknown event", link="/utomunka/23", actor_id=2)
    db.commit()
    assert len(list(db.scalars(select(Notification)))) == 1
    assert list(db.scalars(select(PushDelivery))) == []


def test_disabled_kind_not_enqueued_but_kept_in_inbox(db):
    db.add(NotificationPreference(employee_id=1, kind="mention", enabled=False))
    db.commit()
    notify(db)
    assert db.scalar(select(Notification)) is not None
    assert db.scalar(select(PushDelivery)) is None


def test_disable_after_enqueue_blocks_pending_push(db):
    notify(db)
    db.add(NotificationPreference(employee_id=1, kind="mention", enabled=False))
    db.commit()
    transport = FakeTransport()
    assert process_one(db, transport)
    assert transport.calls == 0


def test_preferences_are_account_and_kind_specific(db):
    db.add(NotificationPreference(employee_id=2, kind="mention", enabled=False))
    db.add(NotificationPreference(employee_id=1, kind="comment", enabled=False))
    db.commit()
    notify(db)
    transport = FakeTransport()
    assert process_one(db, transport)
    assert transport.calls == 1


@pytest.mark.parametrize("kind", ["comment", "bejovo_szamla", "kotelezettseg", "anyagbekeres_leadas", "vagoi_jatek_gyoztes", "vagoi_jatek_nyeremeny"])
def test_supported_categories_push(db, kind):
    create_notification(db, employee_id=1, kind=kind, message="Event", link="/", actor_id=2)
    db.commit()
    transport = FakeTransport()
    assert process_one(db, transport)
    assert transport.calls == 1


def preference_routes():
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("preference_routes_test", Path(__file__).parents[1] / "app/api/routes/notifications.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_partial_preferences_are_owned_and_persisted(db):
    module = preference_routes()
    first = db.get(Employee, 1)
    other = db.get(Employee, 2)
    module.save_preferences(module.PreferenceUpdate(preferences={"mention": False}), db, first)
    module.save_preferences(module.PreferenceUpdate(preferences={"comment": False}), db, first)
    result = module.get_preferences(db, first)["preferences"]
    assert result["mention"] is False and result["comment"] is False
    assert result["assignment"] is True
    assert module.get_preferences(db, other)["preferences"]["mention"] is True
    module.save_preferences(module.PreferenceUpdate(preferences={"mention": True}), db, first)
    assert module.get_preferences(db, first)["preferences"]["mention"] is True


def test_unknown_preferences_and_spoofed_owner_rejected(db):
    from fastapi import HTTPException
    from pydantic import ValidationError
    module = preference_routes()
    with pytest.raises(HTTPException) as error:
        module.save_preferences(module.PreferenceUpdate(preferences={"unknown": False}), db, db.get(Employee, 1))
    assert error.value.status_code == 422
    with pytest.raises(ValidationError):
        module.PreferenceUpdate(preferences={"mention": False}, employee_id=2)
    with pytest.raises(ValidationError):
        module.PreferenceUpdate(preferences={"mention": "false"})


def test_preferences_require_authentication():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    module = preference_routes()
    app = FastAPI()
    app.include_router(module.router)
    app.dependency_overrides[module.get_db] = lambda: None
    client = TestClient(app)
    assert client.get("/notifications/preferences").status_code == 401
    assert client.put("/notifications/preferences", json={"preferences": {"mention": False}}).status_code == 401
