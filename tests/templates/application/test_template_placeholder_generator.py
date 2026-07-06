"""Tests for TemplatePlaceholderGenerator."""

import pytest

from pactus_backend.modules.templates.application.services.template_placeholder_generator import TemplatePlaceholderGenerator


class TestTemplatePlaceholderGenerator:
    def test_infers_placeholder_from_common_field_patterns(self):
        placeholder = TemplatePlaceholderGenerator.build_placeholder(key="gerente_ruc", label="RUC del Gerente", field_type="text")
        assert placeholder == "Ej. 20123456789"

    def test_infers_date_placeholder_from_field_type(self):
        placeholder = TemplatePlaceholderGenerator.build_placeholder(key="fecha_inicio_contrato", label="Fecha de Inicio", field_type="date")
        assert placeholder == "Ej. 2026-12-31"

    def test_infers_time_placeholder_from_field_type(self):
        placeholder = TemplatePlaceholderGenerator.build_placeholder(key="hora_inicio_jornada", label="Hora de Inicio", field_type="time")
        assert placeholder == "Ej. 09:00"

    def test_replaces_instructional_placeholder_with_example(self):
        should_replace = TemplatePlaceholderGenerator.should_autogenerate_placeholder("Ingrese el número de DNI del trabajador")
        assert should_replace is True
        
        # Once determined it should be replaced, build_placeholder generates the proper one
        placeholder = TemplatePlaceholderGenerator.build_placeholder(key="trabajador_dni", label="DNI del Trabajador", field_type="text")
        assert placeholder == "Ej. 12345678"

    def test_infers_literal_placeholder_for_textual_amounts(self):
        placeholder = TemplatePlaceholderGenerator.build_placeholder(key="monto_remuneracion_literal", label="Monto de la Remuneración en letras", field_type="text")
        assert placeholder == "Ej. Monto de la Remuneración en letras"

    def test_infers_canonical_placeholders(self):
        placeholder = TemplatePlaceholderGenerator.build_placeholder(key="salario", label="Salario Base", field_type="number")
        assert placeholder == "Ej. 1500"
