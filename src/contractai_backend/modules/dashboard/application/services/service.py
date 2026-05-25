"""Main dashboard application service class."""

from ..repositories import DashboardRepository
from .alerts import DashboardAlertServiceMixin
from .charts import DashboardChartServiceMixin
from .contracts import DashboardContractServiceMixin
from .helpers import DashboardServiceHelpers
from .rankings import DashboardRankingServiceMixin


class DashboardService(
    DashboardServiceHelpers,
    DashboardChartServiceMixin,
    DashboardAlertServiceMixin,
    DashboardContractServiceMixin,
    DashboardRankingServiceMixin,
):
    """Coordinates dashboard read models and access rules."""

    def __init__(self, repository: DashboardRepository):
        self.repository = repository
