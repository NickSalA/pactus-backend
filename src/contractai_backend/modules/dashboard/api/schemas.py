"""HTTP schemas for dashboard API responses."""

from ..application.dto import (
    AlertCategory as ApplicationAlertCategory,
)
from ..application.dto import (
    AlertColor as ApplicationAlertColor,
)
from ..application.dto import (
    AlertItem as ApplicationAlertItem,
)
from ..application.dto import (
    AreaChartPoint as ApplicationAreaChartPoint,
)
from ..application.dto import (
    AreaChartProps as ApplicationAreaChartProps,
)
from ..application.dto import (
    AreaChartResponse as ApplicationAreaChartResponse,
)
from ..application.dto import (
    AreaChartSeries as ApplicationAreaChartSeries,
)
from ..application.dto import (
    AreaChartYAxis as ApplicationAreaChartYAxis,
)
from ..application.dto import (
    CompanyLoyaltyDashboardResponse as ApplicationCompanyLoyaltyDashboardResponse,
)
from ..application.dto import (
    ContractOriginResponse as ApplicationContractOriginResponse,
)
from ..application.dto import (
    RecentContractResponse as ApplicationRecentContractResponse,
)
from ..application.dto import (
    RetentionDashboardResponse as ApplicationRetentionDashboardResponse,
)
from ..application.dto import (
    TopCompanyResponse as ApplicationTopCompanyResponse,
)
from ..application.dto import (
    TopServiceResponse as ApplicationTopServiceResponse,
)


class AlertColor(ApplicationAlertColor):
    """HTTP response schema for alert color tokens."""


class AlertItem(ApplicationAlertItem):
    """HTTP response schema for one dashboard alert."""


class AlertCategory(ApplicationAlertCategory):
    """HTTP response schema for grouped dashboard alerts."""


class AreaChartPoint(ApplicationAreaChartPoint):
    """HTTP response schema for one chart point."""


class AreaChartYAxis(ApplicationAreaChartYAxis):
    """HTTP response schema for area chart axis metadata."""


class AreaChartSeries(ApplicationAreaChartSeries):
    """HTTP response schema for one chart series."""


class AreaChartProps(ApplicationAreaChartProps):
    """HTTP response schema for area chart props."""


class AreaChartResponse(ApplicationAreaChartResponse):
    """HTTP response schema for area chart data."""


class RecentContractResponse(ApplicationRecentContractResponse):
    """HTTP response schema for recent contracts."""


class TopCompanyResponse(ApplicationTopCompanyResponse):
    """HTTP response schema for top company rows."""


class TopServiceResponse(ApplicationTopServiceResponse):
    """HTTP response schema for top service rows."""


class RetentionDashboardResponse(ApplicationRetentionDashboardResponse):
    """HTTP response schema for worker retention dashboard."""


class ContractOriginResponse(ApplicationContractOriginResponse):
    """HTTP response schema for contract origin dashboard."""


class CompanyLoyaltyDashboardResponse(ApplicationCompanyLoyaltyDashboardResponse):
    """HTTP response schema for B2B client loyalty dashboard."""


__all__ = [
    "AlertCategory",
    "AlertColor",
    "AlertItem",
    "AreaChartPoint",
    "AreaChartProps",
    "AreaChartResponse",
    "AreaChartSeries",
    "AreaChartYAxis",
    "CompanyLoyaltyDashboardResponse",
    "ContractOriginResponse",
    "RecentContractResponse",
    "RetentionDashboardResponse",
    "TopCompanyResponse",
    "TopServiceResponse",
]
