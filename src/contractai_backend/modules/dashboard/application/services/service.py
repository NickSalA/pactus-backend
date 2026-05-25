"""Main dashboard application service class."""

from ..repositories import DashboardRepository
from .alerts import DashboardAlertServiceMixin
from .charts import DashboardChartServiceMixin
from .contracts import DashboardContractServiceMixin
from .helpers import DashboardServiceHelpers
from .loyalty import DashboardCompanyLoyaltyServiceMixin
from .origin import DashboardOriginServiceMixin
from .rankings import DashboardRankingServiceMixin
from .retention import DashboardRetentionServiceMixin


class DashboardService(
    DashboardServiceHelpers,
    DashboardChartServiceMixin,
    DashboardAlertServiceMixin,
    DashboardContractServiceMixin,
    DashboardRankingServiceMixin,
    DashboardRetentionServiceMixin,
    DashboardOriginServiceMixin,
    DashboardCompanyLoyaltyServiceMixin,
):
    """Coordinates dashboard read models and access rules."""

    def __init__(self, repository: DashboardRepository):
        self.repository = repository
