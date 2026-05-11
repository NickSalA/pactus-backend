"""Secrets provider implementation for Azure Key Vault."""

from loguru import logger


class AzureKeyVaultProvider:
    """Proveedor específico para Azure Key Vault con lazy loading."""

    def __init__(self, vault_url: str):
        self.vault_url: str = vault_url
        self._client = None

    @property
    def client(self):
        """Inicializa el cliente de Azure solo cuando se necesita por primera vez."""
        if self._client is None:
            from azure.core.exceptions import AzureError  # noqa: PLC0415
            from azure.identity import DefaultAzureCredential  # noqa: PLC0415
            from azure.keyvault.secrets import SecretClient  # noqa: PLC0415

            logger.debug("Conectando a Azure Key Vault...")
            try:
                self._client = SecretClient(vault_url=self.vault_url, credential=DefaultAzureCredential())
            except AzureError as e:
                raise RuntimeError("Error al inicializar cliente de Azure Key Vault.") from e
        return self._client

    def get_secret(self, secret_name: str) -> str:
        """Obtiene un secreto de Azure Key Vault."""
        from azure.core.exceptions import AzureError, ClientAuthenticationError, ResourceNotFoundError  # noqa: PLC0415

        logger.debug(f"Obteniendo secreto de Azure: {secret_name}")
        try:
            secret = self.client.get_secret(secret_name)
            if secret.value is None:
                raise ValueError(f"El secreto '{secret_name}' no tiene valor.")
            return secret.value
        except ResourceNotFoundError as e:
            raise ValueError(f"Secreto '{secret_name}' no encontrado en Key Vault.") from e
        except ClientAuthenticationError as e:
            raise RuntimeError("No se pudo autenticar con Azure Key Vault.") from e
        except AzureError as e:
            raise RuntimeError(f"No se pudo recuperar el secreto '{secret_name}' desde Azure Key Vault.") from e
