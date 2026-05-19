"""Application DTOs for notification rules."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..domain import NotificationType


class NotificationRuleCreateRequest(BaseModel):
    """Data required to create a notification rule."""

    document_id: int | None = Field(default=None, gt=0)
    days_before_due: int = Field(..., gt=0)
    is_active: bool = True


class NotificationRuleUpdateRequest(BaseModel):
    """Data accepted when updating a notification rule."""

    days_before_due: int | None = Field(default=None, gt=0)
    is_active: bool | None = None

    @model_validator(mode="after")
    def validate_non_empty_patch(self) -> "NotificationRuleUpdateRequest":
        """Requires at least one field in patch requests."""
        if not self.model_fields_set:
            raise ValueError("Patch request cannot be empty")
        return self


class NotificationRuleResponse(BaseModel):
    """Notification rule returned by application use cases."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    document_id: int | None = None
    days_before_due: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class NotificationDocument(BaseModel):
    """Document data needed by notification use cases."""

    id: int | None
    type: str | None = None
    end_date: date
    file_name: str | None = None


class NotificationRecipient(BaseModel):
    """Recipient data needed by notification use cases."""

    id: int | None = None
    organization_id: int
    email: str
    full_name: str | None = None
    is_active: bool
    receives_notifications: bool


class NotificationEvent(BaseModel):
    """Represents a contract alert triggered for the current day."""

    document: NotificationDocument
    days_remaining: int
    notification_type: NotificationType


class SendEmailAlertsResponse(BaseModel):
    """Result returned after sending notification emails manually."""

    emails_sent: int


class CronSendEmailsResponse(SendEmailAlertsResponse):
    """Result returned after processing the daily notification cron."""

    orgs_processed: int
    orgs_skipped: int
