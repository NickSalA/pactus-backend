"""Tests para JinjaRenderer."""

import pytest

from contractai_backend.modules.templates.infrastructure.jinja_render import JinjaRenderer


@pytest.fixture
def renderer() -> JinjaRenderer:
    return JinjaRenderer()


class TestJinjaRenderer:
    @pytest.mark.asyncio
    async def test_renders_simple_variable(self, renderer):
        result = await renderer.render("Hola {{ nombre }}", {"nombre": "Juan"})
        assert result == "Hola Juan"

    @pytest.mark.asyncio
    async def test_renders_multiple_variables(self, renderer):
        result = await renderer.render("{{ a }} y {{ b }}", {"a": "foo", "b": "bar"})
        assert result == "foo y bar"

    @pytest.mark.asyncio
    async def test_renders_template_without_variables(self, renderer):
        result = await renderer.render("Sin variables", {})
        assert result == "Sin variables"

    @pytest.mark.asyncio
    async def test_undefined_variable_raises(self, renderer):
        with pytest.raises(Exception):
            await renderer.render("{{ undefined_var }}", {})

    @pytest.mark.asyncio
    async def test_renders_numeric_value(self, renderer):
        result = await renderer.render("Valor: {{ amount }}", {"amount": 1000})
        assert "1000" in result
