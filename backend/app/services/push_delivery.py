"""Only committed notifications are consumed; failed transactions never send."""
from datetime import datetime, timedelta, timezone
import logging
from sqlalchemy import select
from app.core.database import SessionLocal
from app.models.employee import Employee
from app.models.notification import Notification
from app.models.push import PushDelivery, PushDevice
from app.services.apple_push import ApplePush, PushConfig
from app.services.notification_preferences import enabled

logger = logging.getLogger(__name__)


def enqueue(db, notification):
    if not enabled(db, notification.employee_id, notification.kind):
        return
    # Flush obtains the notification ID inside the caller's transaction.
    db.flush()
    devices = db.scalars(select(PushDevice).where(PushDevice.employee_id == notification.employee_id,
                                                PushDevice.expires_at > datetime.now(timezone.utc)))
    for device in devices:
        db.add(PushDelivery(notification_id=notification.id, device_id=device.id))


def process_one(db, transport, now=None):
    now = now or datetime.now(timezone.utc)
    delivery = db.scalar(select(PushDelivery).where(PushDelivery.completed_at.is_(None),
                         PushDelivery.next_attempt_at <= now).order_by(PushDelivery.id)
                         .with_for_update(skip_locked=True).limit(1))
    if delivery is None:
        return False
    # Serialize with registration/reassignment/logout so an old account's queued
    # messages cannot be delivered to a device now registered to another account.
    device = db.scalar(select(PushDevice).where(PushDevice.id == delivery.device_id).with_for_update())
    notification = db.get(Notification, delivery.notification_id)
    employee = db.get(Employee, notification.employee_id) if notification else None
    def utc(value):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    if (device is None or notification is None or employee is None or employee.is_active is False
            or device.employee_id != notification.employee_id or utc(device.expires_at) <= now
            or not enabled(db, notification.employee_id, notification.kind)
            or notification.is_read or utc(notification.created_at) < now - timedelta(days=1)):
        delivery.result = "skipped"
        delivery.completed_at = now
    else:
        delivery.attempts += 1
        try:
            outcome = transport.send(device, notification)
        except Exception:
            # Avoid token/key/notification contents in log output.
            logger.warning("APNs connection failed for delivery %s", delivery.id)
            outcome = "retry"
        delivery.result = outcome
        if outcome != "retry" or delivery.attempts >= 12:
            delivery.completed_at = now
            if outcome == "invalid_device":
                device.expires_at = now
        else:
            delivery.next_attempt_at = now + timedelta(seconds=min(3600, 15 * 2 ** delivery.attempts))
    db.commit()
    return True


def start_worker(stop):
    if not PushConfig.load().enabled:
        return
    transport = ApplePush()
    try:
        while not stop.is_set():
            try:
                with SessionLocal() as db:
                    worked = process_one(db, transport)
            except Exception:
                logger.warning("Push delivery cycle failed; retrying later")
                worked = False
            if not worked:
                stop.wait(5)
    finally:
        transport.client.close()
