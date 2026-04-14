"""Módulo encargado de renderizar las plantillas Markdown utilizando Jinja2."""

from datetime import date, datetime
from typing import Any

from jinja2 import Environment, StrictUndefined

from ..application.repositories.base_render import ITemplateRenderer


class JinjaRenderer(ITemplateRenderer):
    def __init__(self):
        self.env = Environment(undefined=StrictUndefined)
        self.env.filters["format_date"] = self._format_date

    async def render(self, template_md: str, payload: dict[str, Any]) -> str:
        """Toma el molde (Markdown con llaves) y el diccionario de datos. Retorna el Markdown final inyectado."""
        template = self.env.from_string(template_md)
        template = template.render(**payload)
        return template

    def _format_date(self, value: Any, fmt: str) -> str:
        """Formats ISO-like date values for supported template expressions."""
        if value in (None, ""):
            return ""

        if isinstance(value, datetime):
            parsed_value = value
        elif isinstance(value, date):
            parsed_value = datetime.combine(value, datetime.min.time())
        elif isinstance(value, str):
            parsed_value = self._parse_datetime(value)
            if parsed_value is None:
                return value
        else:
            return str(value)

        return parsed_value.strftime(fmt)

    def _parse_datetime(self, value: str) -> datetime | None:
        """Parses common ISO date and datetime strings."""
        cleaned = value.strip()
        if not cleaned:
            return None

        try:
            return datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
        except ValueError:
            pass

        try:
            return datetime.combine(date.fromisoformat(cleaned), datetime.min.time())
        except ValueError:
            return None
