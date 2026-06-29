"""PayPal API adapter for subscription verification."""

import httpx
from loguru import logger

from ....core.exceptions.base import ServiceUnavailableError
from ....modules.billing.application.dto import PayPalSubscriptionDetails
from ....modules.billing.application.repositories import PayPalSubscriptionGateway
from ....modules.billing.domain.exceptions import PayPalServiceError, PayPalSubscriptionValidationError


class PayPalSubscriptionAdapter(PayPalSubscriptionGateway):
    """Verifies PayPal subscription data through PayPal's REST API."""

    def __init__(self, client: httpx.AsyncClient, client_id: str | None, client_secret: str | None, base_url: str):
        self.client = client
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url.rstrip("/")

    async def get_subscription(self, subscription_id: str) -> PayPalSubscriptionDetails:
        """Fetch and normalize a PayPal subscription."""
        token = await self._get_access_token()
        try:
            response = await self.client.get(
                f"{self.base_url}/v1/billing/subscriptions/{subscription_id}",
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                timeout=15.0,
            )
        except httpx.RequestError as exc:
            raise PayPalServiceError("No se pudo consultar la suscripción en PayPal.") from exc

        if response.status_code == httpx.codes.NOT_FOUND:
            raise PayPalSubscriptionValidationError("La suscripción de PayPal no existe.")
        if response.status_code != httpx.codes.OK:
            raise PayPalServiceError()

        data = response.json()
        paypal_id = str(data.get("id") or "").strip()
        custom_id = str(data.get("custom_id") or "").strip()
        if paypal_id != subscription_id or not custom_id:
            raise PayPalSubscriptionValidationError("La suscripción de PayPal no contiene los datos esperados.")
        return PayPalSubscriptionDetails(id=paypal_id, custom_id=custom_id)

    async def get_subscription_status(self, subscription_id: str) -> str:
        """Return the current status of a PayPal subscription."""
        try:
            token = await self._get_access_token()
            response = await self.client.get(
                f"{self.base_url}/v1/billing/subscriptions/{subscription_id}",
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                timeout=15.0,
            )
            if response.status_code != httpx.codes.OK:
                return "UNKNOWN"
            data = response.json()
            return str(data.get("status", "UNKNOWN")).strip().upper()
        except (httpx.RequestError, PayPalServiceError, ServiceUnavailableError):
            logger.warning("No se pudo verificar el estado de la suscripción en PayPal")
            return "UNKNOWN"

    async def _get_access_token(self) -> str:
        if not self.client_id or not self.client_secret:
            raise ServiceUnavailableError("PayPal no está configurado en el backend.")
        try:
            response = await self.client.post(
                f"{self.base_url}/v1/oauth2/token",
                data={"grant_type": "client_credentials"},
                auth=(self.client_id, self.client_secret),
                headers={"Accept": "application/json"},
                timeout=15.0,
            )
        except httpx.RequestError as exc:
            raise PayPalServiceError("No se pudo autenticar con PayPal.") from exc

        if response.status_code != httpx.codes.OK:
            raise PayPalServiceError("PayPal rechazó las credenciales configuradas.")

        token = str(response.json().get("access_token") or "").strip()
        if not token:
            raise PayPalServiceError("PayPal no devolvió un token de acceso válido.")
        return token
