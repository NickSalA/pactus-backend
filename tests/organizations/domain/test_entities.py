"""Tests para entidades del dominio de organizaciones."""

from contractai_backend.modules.organizations.domain.entities import OrganizationTable


def test_organization_default_is_active():
    org = OrganizationTable(name="Acme Corp")
    assert org.is_active is True


def test_organization_name_stored():
    org = OrganizationTable(name="Mi Empresa")
    assert org.name == "Mi Empresa"


def test_organization_optional_fields_default_none():
    org = OrganizationTable(name="Test")
    assert org.ruc is None
    assert org.email is None
    assert org.phone is None
