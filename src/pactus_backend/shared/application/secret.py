"""Módulo que define la interfaz estándar para los proveedores de secretos en la aplicación."""

from typing import Protocol


class SecretsProvider(Protocol):
    """Interfaz estándar para todos los proveedores de secretos."""

    def get_secret(self, secret_name: str) -> str:
        """Obtiene el valor de un secreto dado su nombre."""
        pass


class SecretsRegistry:
    """Clase que actúa como registro central del proveedor de secretos."""

    _provider: SecretsProvider | None = None

    @classmethod
    def set_provider(cls, provider: SecretsProvider) -> None:
        """Configura el proveedor de secretos a utilizar en la aplicación."""
        cls._provider = provider

    @classmethod
    def get_secret(cls, name: str) -> str:
        """Obtiene un secreto utilizando el proveedor configurado."""
        return None if cls._provider is None else cls._provider.get_secret(name)  # type: ignore

def get_secret(name: str) -> str:
    """Función de conveniencia para obtener secretos desde cualquier parte del código."""
    return SecretsRegistry.get_secret(name)
