"""Tests for Jinja template rendering helpers."""

import pytest

from pactus_backend.modules.templates.infrastructure.jinja_render import JinjaRenderer


class TestJinjaRenderer:
    @pytest.mark.asyncio
    async def test_render_supports_format_date_filter(self):
        renderer = JinjaRenderer()

        rendered = await renderer.render(
            template_md="Inicio: {{ fecha_inicio_contrato | format_date('%d/%m/%Y') }}",
            payload={"fecha_inicio_contrato": "2026-04-14"},
        )

        assert rendered == "Inicio: 14/04/2026"

    @pytest.mark.asyncio
    async def test_render_supports_format_date_components(self):
        renderer = JinjaRenderer()

        rendered = await renderer.render(
            template_md=(
                "Inicio: {{ fecha_inicio_contrato | format_date('%d') }}/"
                "{{ fecha_inicio_contrato | format_date('%m') }}/"
                "{{ fecha_inicio_contrato | format_date('%Y') }}"
            ),
            payload={"fecha_inicio_contrato": "2026-04-14"},
        )

        assert rendered == "Inicio: 14/04/2026"
