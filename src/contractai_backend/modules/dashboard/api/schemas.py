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
    RecentContractResponse as ApplicationRecentContractResponse,
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

__all__ = [
    "AlertCategory",
    "AlertColor",
    "AlertItem",
    "AreaChartPoint",
    "AreaChartProps",
    "AreaChartResponse",
    "AreaChartSeries",
    "AreaChartYAxis",
    "RecentContractResponse",
    "TopCompanyResponse",
    "TopServiceResponse",
]
