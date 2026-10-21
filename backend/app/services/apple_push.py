"""APNs transport. All secrets remain server-side. Disabled until configured."""
from dataclasses import dataclass
import json
import os
import time
import uuid
import httpx
from jose import jwt


@dataclass(frozen=True)
class PushConfig:
    key_id: str
    team_id: str
    private_key: str
    topic: str

    @classmethod
    def load(cls):
        return cls(os.getenv("APNS_KEY_ID", ""), os.getenv("APNS_TEAM_ID", ""),
                   os.getenv("APNS_PRIVATE_KEY", "").replace("\\n", "\n"), os.getenv("APNS_TOPIC", ""))

    @property
    def enabled(self):
        return bool(self.key_id and self.team_id and self.private_key and self.topic)


def payload(notification):
    titles = {"mention": "Megjelöltek", "assignment": "Új feladatod érkezett", "call_sheet": "Új diszpód érkezett"}
    value = {"aps": {"alert": {"title": titles.get(notification.kind, "HYPE OS"),
                               "body": notification.message[:500]}, "sound": "default",
                     "thread-id": "hype-" + notification.kind},
             "kind": notification.kind, "notification_id": notification.id, "employee_id": notification.employee_id,
             "link": notification.link}
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class ApplePush:
    def __init__(self, config=None, client=None):
        self.config = config or PushConfig.load()
        self.client = client or httpx.Client(http2=True, timeout=10)
        self._jwt = None
        self._issued = 0

    def send(self, device, notification):
        if not self.config.enabled:
            raise RuntimeError("APNs is not configured")
        now = int(time.time())
        if self._jwt is None or now - self._issued >= 3000:
            self._jwt = jwt.encode({"iss": self.config.team_id, "iat": now}, self.config.private_key,
                                   algorithm="ES256", headers={"kid": self.config.key_id})
            self._issued = now
        host = "api.sandbox.push.apple.com" if device.environment == "sandbox" else "api.push.apple.com"
        response = self.client.post(f"https://{host}/3/device/{device.token}", content=payload(notification), headers={
            "authorization": "bearer " + self._jwt, "apns-topic": self.config.topic,
            "apns-push-type": "alert", "apns-priority": "10", "content-type": "application/json",
            "apns-id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"hype:{notification.id}:{device.id}")),
            "apns-collapse-id": f"notification-{notification.id}",
            "apns-expiration": str(int(notification.created_at.timestamp()) + 86400),
        })
        if response.status_code == 200:
            return "sent"
        try:
            reason = response.json().get("reason", "")
        except ValueError:
            reason = ""
        if response.status_code == 410 or reason in {"BadDeviceToken", "DeviceTokenNotForTopic", "Unregistered"}:
            return "invalid_device"
        if reason in {"ExpiredProviderToken", "InvalidProviderToken"}:
            self._jwt = None
        if response.status_code == 413:
            return "invalid_payload"
        return "retry"
