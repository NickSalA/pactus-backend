"""Handlers for dashboard chart generation within the LangGraph agent."""

import json

from ....dashboard.application.services import DashboardService
from ....documents.domain.value_objs import CurrencyType
from ....users.domain.entities import UserTable


async def handle_top_services(service: DashboardService, user: UserTable, currency: str | None, limit: int | None) -> str:
    resolved_currency = CurrencyType(currency) if currency else None

    # Validar el limite
    safe_limit = limit if limit is not None and 1 <= limit <= 20 else None

    rows = await service.get_top_services(current_user=user, currency=resolved_currency, limit=safe_limit)

    chart_data = {
        "type": "bar",
        "layout": "horizontal",
        "title": f"Top Servicios por Monto{f' ({currency})' if currency else ''}",
        "config": {
            "categoryKey": "name",
            "series": [
                {"dataKey": "amount", "name": "Monto Total", "color": "#6366F1"},
            ],
        },
        "data": [{"name": row.name, "amount": row.amount, "quantity": row.quantity} for row in rows],
    }
    return json.dumps({"status": "success", "chart": chart_data}, ensure_ascii=True)


async def handle_top_companies(service: DashboardService, user: UserTable, currency: str | None, limit: int | None) -> str:
    resolved_currency = CurrencyType(currency) if currency else None
    safe_limit = limit if limit is not None and 1 <= limit <= 20 else None

    rows = await service.get_top_companies(current_user=user, currency=resolved_currency, limit=safe_limit)

    chart_data = {
        "type": "bar",
        "layout": "horizontal",
        "title": f"Top Clientes por Volumen{f' ({currency})' if currency else ''}",
        "config": {
            "categoryKey": "name",
            "series": [
                {"dataKey": "amount", "name": "Monto Total", "color": "#10B981"},
            ],
        },
        "data": [{"name": row.name, "amount": row.amount, "contracts": row.contracts} for row in rows],
    }
    return json.dumps({"status": "success", "chart": chart_data}, ensure_ascii=True)


async def handle_retention(service: DashboardService, user: UserTable) -> str:
    dashboard = await service.get_labor_retention_dashboard(current_user=user)

    chart_data = {
        "type": "line",
        "layout": "horizontal",
        "title": "Tendencia de Retencion Laboral",
        "config": {
            "categoryKey": "month",
            "series": [
                {"dataKey": "renewal_rate", "name": "Tasa de Renovacion (%)", "color": "#3B82F6"},
            ],
        },
        "data": [{"month": row.month, "renewal_rate": round(row.renewal_rate * 100, 2)} for row in dashboard.renewal_trend],
    }
    return json.dumps({"status": "success", "chart": chart_data}, ensure_ascii=True)


async def handle_loyalty(service: DashboardService, user: UserTable) -> str:
    dashboard = await service.get_company_loyalty_dashboard(current_user=user)

    chart_data = {
        "type": "line",
        "layout": "horizontal",
        "title": "Tendencia de Fidelidad de Clientes (B2B)",
        "config": {
            "categoryKey": "month",
            "series": [
                {"dataKey": "renewal_rate", "name": "Tasa de Renovacion (%)", "color": "#F59E0B"},
            ],
        },
        "data": [{"month": row.month, "renewal_rate": round(row.renewal_rate * 100, 2)} for row in dashboard.renewal_trend],
    }
    return json.dumps({"status": "success", "chart": chart_data}, ensure_ascii=True)


async def handle_origin(service: DashboardService, user: UserTable) -> str:
    dashboard = await service.get_labor_origin_dashboard(current_user=user)

    chart_data = {
        "type": "pie",
        "layout": "centric",
        "title": "Origen de Contratos Laborales",
        "config": {
            "categoryKey": "origin_type",
            "series": [
                {"dataKey": "count", "name": "Cantidad", "color": "#8B5CF6"},
            ],
        },
        "data": [{"origin_type": row.origin_type, "count": row.count, "percentage": round(row.percentage, 2)} for row in dashboard.distribution],
    }
    return json.dumps({"status": "success", "chart": chart_data}, ensure_ascii=True)
