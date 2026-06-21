"""Repository and external service ports for billing."""

from abc import ABC, abstractmethod

from contractai_backend.modules.billing.application.dto import PayPalSubscriptionDetails
from contractai_backend.modules.organizations.domain.entities import OrganizationTable
from contractai_backend.modules.users.domain.entities import UserTable


class PayPalSubscriptionGateway(ABC):
    """External gateway used to verify PayPal subscriptions."""

    @abstractmethod
    async def get_subscription(self, subscription_id: str) -> PayPalSubscriptionDetails:
        """Return subscription data from PayPal."""
        pass


class BillingProvisioningRepository(ABC):
    """Persistence port for subscription-driven organization provisioning."""

    @abstractmethod
    async def get_organization_by_paypal_subscription_id(self, subscription_id: str) -> OrganizationTable | None:
        """Return the organization associated with a PayPal subscription ID."""
        pass

    @abstractmethod
    async def get_user_by_email(self, email: str) -> UserTable | None:
        """Return a user by email."""
        pass

    @abstractmethod
    async def create_pending_organization_with_admin(
        self,
        *,
        admin_email: str,
        organization_name: str,
        paypal_subscription_id: str,
    ) -> OrganizationTable:
        """Create a placeholder organization and its initial admin in one transaction."""
        pass
