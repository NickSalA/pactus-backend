"""Tests for PayPal subscription confirmation service."""

import pytest

from pactus_backend.modules.billing.application.dto import ConfirmPayPalSubscriptionRequest, PayPalSubscriptionDetails
from pactus_backend.modules.billing.application.services import PayPalSubscriptionService
from pactus_backend.modules.billing.domain.exceptions import PayPalSubscriptionConflictError, PayPalSubscriptionValidationError
from pactus_backend.modules.organizations.domain.entities import OrganizationTable
from pactus_backend.modules.users.domain.entities import UserTable
from pactus_backend.modules.users.domain.value_objs import UserRole


class FakePayPalGateway:
    def __init__(self, custom_id: str = "admin@example.com", status: str = "ACTIVE"):
        self.custom_id = custom_id
        self.status = status
        self.subscription_ids: list[str] = []
        self.status_subscription_ids: list[str] = []

    async def get_subscription(self, subscription_id: str) -> PayPalSubscriptionDetails:
        self.subscription_ids.append(subscription_id)
        return PayPalSubscriptionDetails(id=subscription_id, custom_id=self.custom_id)

    async def get_subscription_status(self, subscription_id: str) -> str:
        self.status_subscription_ids.append(subscription_id)
        return self.status


class FakeProvisioningRepository:
    def __init__(self, existing_organization: OrganizationTable | None = None, existing_user: UserTable | None = None):
        self.existing_organization = existing_organization
        self.existing_user = existing_user
        self.created_payload: dict[str, str] | None = None

    async def get_organization_by_paypal_subscription_id(self, _subscription_id: str) -> OrganizationTable | None:
        return self.existing_organization

    async def get_organization_by_id(self, _organization_id: int) -> OrganizationTable | None:
        return self.existing_organization

    async def get_user_by_email(self, _email: str) -> UserTable | None:
        return self.existing_user

    async def create_pending_organization_with_admin(
        self,
        *,
        admin_email: str,
        organization_name: str,
        paypal_subscription_id: str,
    ) -> OrganizationTable:
        self.created_payload = {
            "admin_email": admin_email,
            "organization_name": organization_name,
            "paypal_subscription_id": paypal_subscription_id,
        }
        return OrganizationTable(id=10, name=organization_name, paypal_subscription_id=paypal_subscription_id)


def _request() -> ConfirmPayPalSubscriptionRequest:
    return ConfirmPayPalSubscriptionRequest(subscription_id="I-6Y983831YP445233M", email="ADMIN@EXAMPLE.COM")


class TestPayPalSubscriptionService:
    @pytest.mark.asyncio
    async def test_confirms_subscription_and_creates_pending_organization(self):
        gateway = FakePayPalGateway(custom_id="admin@example.com")
        repository = FakeProvisioningRepository()
        service = PayPalSubscriptionService(paypal_gateway=gateway, provisioning_repository=repository)

        result = await service.confirm_subscription(_request())

        assert result.organization_id == 10
        assert result.admin_email == "admin@example.com"
        assert result.paypal_subscription_id == "I-6Y983831YP445233M"
        assert repository.created_payload == {
            "admin_email": "admin@example.com",
            "organization_name": "Pending organization I-6Y983831YP445233M",
            "paypal_subscription_id": "I-6Y983831YP445233M",
        }

    @pytest.mark.asyncio
    async def test_rejects_subscription_when_paypal_email_does_not_match(self):
        gateway = FakePayPalGateway(custom_id="other@example.com")
        repository = FakeProvisioningRepository()
        service = PayPalSubscriptionService(paypal_gateway=gateway, provisioning_repository=repository)

        with pytest.raises(PayPalSubscriptionValidationError):
            await service.confirm_subscription(_request())

    @pytest.mark.asyncio
    async def test_rejects_when_email_already_exists(self):
        gateway = FakePayPalGateway(custom_id="admin@example.com")
        repository = FakeProvisioningRepository(
            existing_user=UserTable(id=5, organization_id=20, email="admin@example.com", role=UserRole.ADMIN)
        )
        service = PayPalSubscriptionService(paypal_gateway=gateway, provisioning_repository=repository)

        with pytest.raises(PayPalSubscriptionConflictError):
            await service.confirm_subscription(_request())

    @pytest.mark.asyncio
    async def test_returns_existing_provision_when_same_subscription_and_admin_are_retried(self):
        gateway = FakePayPalGateway(custom_id="admin@example.com")
        organization = OrganizationTable(id=7, name="Pending organization I-6Y983831YP445233M", paypal_subscription_id="I-6Y983831YP445233M")
        user = UserTable(id=5, organization_id=7, email="admin@example.com", role=UserRole.ADMIN)
        repository = FakeProvisioningRepository(existing_organization=organization, existing_user=user)
        service = PayPalSubscriptionService(paypal_gateway=gateway, provisioning_repository=repository)

        result = await service.confirm_subscription(_request())

        assert result.organization_id == 7
        assert result.admin_email == "admin@example.com"
        assert result.paypal_subscription_id == "I-6Y983831YP445233M"
        assert repository.created_payload is None

    @pytest.mark.asyncio
    async def test_check_subscription_active_returns_true_for_active_paypal_subscription(self):
        organization = OrganizationTable(id=7, name="Acme", paypal_subscription_id="I-ACTIVE123")
        gateway = FakePayPalGateway(status="ACTIVE")
        repository = FakeProvisioningRepository(existing_organization=organization)
        service = PayPalSubscriptionService(paypal_gateway=gateway, provisioning_repository=repository)

        result = await service.check_subscription_active(organization_id=7)

        assert result is True
        assert gateway.status_subscription_ids == ["I-ACTIVE123"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("paypal_status,org_id", [("CANCELLED", 11), ("SUSPENDED", 14)])
    async def test_check_subscription_active_returns_false_for_inactive_paypal_statuses(self, paypal_status: str, org_id: int):
        organization = OrganizationTable(id=org_id, name="Acme", paypal_subscription_id="I-INACTIVE123")
        gateway = FakePayPalGateway(status=paypal_status)
        repository = FakeProvisioningRepository(existing_organization=organization)
        service = PayPalSubscriptionService(paypal_gateway=gateway, provisioning_repository=repository)

        result = await service.check_subscription_active(organization_id=org_id)

        assert result is False
        assert gateway.status_subscription_ids == ["I-INACTIVE123"]

    @pytest.mark.asyncio
    async def test_check_subscription_active_returns_false_when_organization_does_not_exist(self):
        gateway = FakePayPalGateway(status="ACTIVE")
        repository = FakeProvisioningRepository(existing_organization=None)
        service = PayPalSubscriptionService(paypal_gateway=gateway, provisioning_repository=repository)

        result = await service.check_subscription_active(organization_id=999)

        assert result is False
        assert gateway.status_subscription_ids == []

    @pytest.mark.asyncio
    async def test_check_subscription_active_returns_true_for_legacy_organization_without_subscription_id(self):
        """Legacy organizations without PayPal ID pass through if they are active."""
        organization = OrganizationTable(id=12, name="Acme", paypal_subscription_id=None, is_active=True)
        gateway = FakePayPalGateway(status="ACTIVE")
        repository = FakeProvisioningRepository(existing_organization=organization)
        service = PayPalSubscriptionService(paypal_gateway=gateway, provisioning_repository=repository)

        result = await service.check_subscription_active(organization_id=12)

        assert result is True
        assert gateway.status_subscription_ids == []

    @pytest.mark.asyncio
    async def test_check_subscription_active_returns_false_for_inactive_legacy_organization_without_subscription_id(self):
        """Inactive legacy organizations without PayPal ID should be blocked."""
        organization = OrganizationTable(id=13, name="Acme", paypal_subscription_id=None, is_active=False)
        gateway = FakePayPalGateway(status="ACTIVE")
        repository = FakeProvisioningRepository(existing_organization=organization)
        service = PayPalSubscriptionService(paypal_gateway=gateway, provisioning_repository=repository)

        result = await service.check_subscription_active(organization_id=13)

        assert result is False
        assert gateway.status_subscription_ids == []
