"""Application services for billing workflows."""

from contractai_backend.modules.billing.application.dto import ConfirmPayPalSubscriptionRequest, ConfirmPayPalSubscriptionResponse
from contractai_backend.modules.billing.application.repositories import BillingProvisioningRepository, PayPalSubscriptionGateway
from contractai_backend.modules.billing.domain.exceptions import PayPalSubscriptionConflictError, PayPalSubscriptionValidationError
from contractai_backend.modules.organizations.domain.entities import OrganizationTable
from contractai_backend.modules.users.domain.entities import UserTable
from contractai_backend.modules.users.domain.value_objs import UserRole


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

    @staticmethod
    def _build_response(organization: OrganizationTable, admin_email: str) -> ConfirmPayPalSubscriptionResponse:
        return ConfirmPayPalSubscriptionResponse(
            organization_id=organization.id,
            admin_email=admin_email,
            paypal_subscription_id=organization.paypal_subscription_id or "",
        )
