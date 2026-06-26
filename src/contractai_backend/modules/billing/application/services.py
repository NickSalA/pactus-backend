"""Application services for billing workflows."""

import time

from contractai_backend.modules.billing.application.dto import ConfirmPayPalSubscriptionRequest, ConfirmPayPalSubscriptionResponse
from contractai_backend.modules.billing.application.repositories import BillingProvisioningRepository, PayPalSubscriptionGateway
from contractai_backend.modules.billing.domain.exceptions import PayPalSubscriptionConflictError, PayPalSubscriptionValidationError
from contractai_backend.modules.organizations.domain.entities import OrganizationTable
from contractai_backend.modules.users.domain.entities import UserTable
from contractai_backend.modules.users.domain.value_objs import UserRole

_cache: dict[int, tuple[bool, float]] = {}

# Tiempo por minutos
_TTL = 10 * 60

class PayPalSubscriptionService:
    """Confirms PayPal subscriptions and provisions the first organization admin."""

    def __init__(self, paypal_gateway: PayPalSubscriptionGateway, provisioning_repository: BillingProvisioningRepository):
        self.paypal_gateway = paypal_gateway
        self.provisioning_repository = provisioning_repository

    async def confirm_subscription(self, payload: ConfirmPayPalSubscriptionRequest) -> ConfirmPayPalSubscriptionResponse:
        """Validate a PayPal subscription and create the initial organization/admin."""
        subscription = await self.paypal_gateway.get_subscription(payload.subscription_id)
        if subscription.custom_id.strip().lower() != payload.email:
            raise PayPalSubscriptionValidationError("El correo no coincide con la suscripción aprobada por PayPal.")

        existing_organization = await self.provisioning_repository.get_organization_by_paypal_subscription_id(payload.subscription_id)
        if existing_organization is not None:
            existing_user = await self.provisioning_repository.get_user_by_email(payload.email)
            if existing_user is not None and existing_user.organization_id == existing_organization.id and existing_user.role == UserRole.ADMIN:
                return self._build_response(organization=existing_organization, admin_email=existing_user.email)
            raise PayPalSubscriptionConflictError()

        existing_user: UserTable | None = await self.provisioning_repository.get_user_by_email(payload.email)
        if existing_user is not None:
            raise PayPalSubscriptionConflictError("Ya existe un usuario registrado con ese correo.")

        organization = await self.provisioning_repository.create_pending_organization_with_admin(
            admin_email=payload.email,
            organization_name=f"Pending organization {payload.subscription_id}",
            paypal_subscription_id=payload.subscription_id,
        )
        return self._build_response(organization=organization, admin_email=payload.email)

    async def check_subscription_active(self, organization_id: int) -> bool:
        """Check if an organization has an active PayPal subscription.

        Results are cached in memory for 5 minutes to avoid hitting PayPal on every request.
        Legacy organizations (no paypal_subscription_id) pass through if they are active.
        """
        now = time.time()
        cached = _cache.get(organization_id)
        if cached and now - cached[1] < _TTL:
            return cached[0]

        organization = await self.provisioning_repository.get_organization_by_id(organization_id)
        if not organization:
            _cache[organization_id] = (False, now)
            return False
        if not organization.paypal_subscription_id:
            _cache[organization_id] = (organization.is_active, now)
            return organization.is_active

        status = await self.paypal_gateway.get_subscription_status(organization.paypal_subscription_id)
        is_active = status == "ACTIVE"
        _cache[organization_id] = (is_active, now)
        return is_active

    @staticmethod
    def _build_response(organization: OrganizationTable, admin_email: str) -> ConfirmPayPalSubscriptionResponse:
        return ConfirmPayPalSubscriptionResponse(
            organization_id=organization.id,
            admin_email=admin_email,
            paypal_subscription_id=organization.paypal_subscription_id or "",
        )
