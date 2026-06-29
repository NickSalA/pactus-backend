from abc import ABC, abstractmethod


class ICloudIntegrationProvider(ABC):
    @abstractmethod
    def get_auth_url(self) -> str:
        pass

    @abstractmethod
    async def exchange_code_for_token(self, code: str) -> dict:
        pass

    @abstractmethod
    async def get_file_metadata(self, token: dict, file_id: str) -> dict:
        pass

    @abstractmethod
    async def download_file(self, token: dict, file_id: str) -> bytes:
        pass
