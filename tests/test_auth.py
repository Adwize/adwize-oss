"""Test optional API key authentication."""

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from api.auth import check_api_key


class TestOptionalApiKey:
    @pytest.mark.asyncio
    async def test_no_api_key_configured_allows_all(self):
        with patch("api.auth.get_settings") as mock_settings:
            mock_settings.return_value.api_key = None
            await check_api_key(x_api_key=None)

    @pytest.mark.asyncio
    async def test_no_api_key_configured_ignores_header(self):
        with patch("api.auth.get_settings") as mock_settings:
            mock_settings.return_value.api_key = None
            await check_api_key(x_api_key="anything")

    @pytest.mark.asyncio
    async def test_valid_api_key_passes(self):
        with patch("api.auth.get_settings") as mock_settings:
            mock_settings.return_value.api_key = "secret-key"
            await check_api_key(x_api_key="secret-key")

    @pytest.mark.asyncio
    async def test_invalid_api_key_rejected(self):
        with patch("api.auth.get_settings") as mock_settings:
            mock_settings.return_value.api_key = "secret-key"
            with pytest.raises(HTTPException) as exc_info:
                await check_api_key(x_api_key="wrong-key")
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_api_key_rejected_when_configured(self):
        with patch("api.auth.get_settings") as mock_settings:
            mock_settings.return_value.api_key = "secret-key"
            with pytest.raises(HTTPException) as exc_info:
                await check_api_key(x_api_key=None)
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_empty_api_key_rejected_when_configured(self):
        with patch("api.auth.get_settings") as mock_settings:
            mock_settings.return_value.api_key = "secret-key"
            with pytest.raises(HTTPException) as exc_info:
                await check_api_key(x_api_key="")
            assert exc_info.value.status_code == 401
