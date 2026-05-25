"""PostgreSQL implementation for dashboard analytics composing query mixins."""

from sqlmodel.ext.asyncio.session import AsyncSession

from ...application.repositories import DashboardRepository
from .alerts import DashboardAlertQueriesMixin
from .charts import DashboardChartQueriesMixin
from .contracts import DashboardContractQueriesMixin
from .helpers import DashboardRepositoryHelpers
from .rankings import DashboardRankingQueriesMixin


class SQLModelDashboardRepository(
    DashboardChartQueriesMixin,
    DashboardAlertQueriesMixin,
    DashboardContractQueriesMixin,
    DashboardRankingQueriesMixin,
    DashboardRepositoryHelpers,
    DashboardRepository,
):
    """Dashboard repository backed by PostgreSQL via SQLModel."""

    def __init__(self, session: AsyncSession):
        self.session = session
