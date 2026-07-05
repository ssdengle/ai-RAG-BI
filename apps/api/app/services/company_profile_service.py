from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.core.errors import DomainError
from apps.api.app.core.logging import get_logger
from apps.api.app.domain.bi import CompanyProfile, CompanyProfileDetail
from apps.api.app.repositories.bi_repository import BiRepository


class CompanyProfileService:
    def __init__(self, *, bi_repository: BiRepository) -> None:
        self._bi_repository = bi_repository
        self._logger = get_logger("api.company_profile_service")

    async def create_company_profile(
        self,
        session: AsyncSession,
        *,
        name: str,
        display_name: str,
        industry: str | None = None,
        description: str | None = None,
        metadata: dict | None = None,
    ) -> CompanyProfile:
        existing = await self._bi_repository.get_company_profile_by_name(session, name)
        if existing is not None:
            raise DomainError(
                "Company profile already exists.",
                details=name,
                code="company_profile_exists",
                status_code=409,
            )

        profile = await self._bi_repository.create_company_profile(
            session,
            name=name,
            display_name=display_name,
            industry=industry,
            description=description,
            metadata=metadata,
        )
        await session.commit()
        self._logger.info("company_profile.created", company_id=profile.company_id, name=name)
        return profile

    async def list_company_profiles(self, session: AsyncSession) -> list[CompanyProfile]:
        return await self._bi_repository.list_company_profiles(session)

    async def get_company_profile(
        self,
        session: AsyncSession,
        *,
        company_id: str,
    ) -> CompanyProfileDetail:
        detail = await self._bi_repository.get_company_profile_detail(session, company_id)
        if detail is None:
            raise DomainError(
                "Company profile was not found.",
                details=company_id,
                code="company_profile_not_found",
                status_code=404,
            )
        return detail
