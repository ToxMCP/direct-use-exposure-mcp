"""Repository worksheet formats; these are not MCP contracts or approvals."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReviewModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReviewScope(ReviewModel):
    chemical_id: str = Field(min_length=1)
    material: str = Field(min_length=1)
    population: str = Field(min_length=1)
    region: str = Field(min_length=1)
    period: str = Field(min_length=1)
    duration: str = Field(min_length=1)
    endpoint: str = Field(min_length=1)
    dose_basis: Literal[
        "external_mg_kg_day", "absorbed_mg_kg_day", "local_skin", "local_respiratory"
    ]
    body_weight_kg: float | None = Field(default=None, gt=0, allow_inf_nan=False)


class AbsorptionSelection(ReviewModel):
    value: str | None = None
    unit: Literal["percent", "fraction"] = "percent"
    statistic: Literal["mean_plus_one_sd", "mean", "p95", "bound", "unknown"] = "unknown"
    applicability: Literal["published_reconstruction", "reviewed", "unknown", "rejected"] = (
        "unknown"
    )
    rationale: str = Field(min_length=1)
    source_ids: list[str] = Field(default_factory=list)
    tested_material: str | None = None
    assessed_material: str | None = None
    tested_formulation: str | None = None
    assessed_formulation: str | None = None
    tested_concentration_percent: str | None = None
    contact_conditions: str | None = None
    study_model: str | None = None
    quality_appraisal: str | None = None


class ReviewComponent(ReviewModel):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]+$", max_length=80)
    scope: ReviewScope
    role: Literal["additive", "alternative", "already_counted", "unknown"]
    overlap_with: list[str] = Field(default_factory=list)
    independence_review: str | None = None
    nature: Literal["documented", "illustrative_reconstruction", "hypothetical"]
    dose_statistic: Literal["deterministic", "mean", "marginal_p95", "unknown"]
    source_ids: list[str] = Field(default_factory=list)
    producer_tool: Literal[
        "exposure_build_screening_exposure_scenario", "exposure_build_inhalation_screening_scenario"
    ] = "exposure_build_screening_exposure_scenario"
    producer_request: dict[str, Any]
    absorption: AbsorptionSelection | None = None
    non_detect: bool = False
    concentration_upper_bound_fraction: str | None = None
    check_pbpk_export: bool = False


class OmittedSource(ReviewModel):
    id: str
    description: str
    upper_bound: str | None = None
    unit: str | None = None
    source_ids: list[str] = Field(default_factory=list)
    reopening_condition: str = Field(min_length=1)


class ReviewWorksheet(ReviewModel):
    schema_version: Literal["exposureReviewWorksheet.v1"]
    id: str
    title: str
    scope: ReviewScope
    reference_cases: list[str] = Field(default_factory=list)
    components: list[ReviewComponent] = Field(default_factory=list, max_length=50)
    omitted_sources: list[OmittedSource] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_components(self) -> ReviewWorksheet:
        if len({x.id for x in self.components}) != len(self.components):
            raise ValueError(
                "Component IDs must be unique; duplicate events require explicit review."
            )
        return self


class ReviewServer(ReviewModel):
    source_checkout: str
    python: str
    expected_version: str
    expected_commit: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")


class ReviewServers(ReviewModel):
    schema_version: Literal["exposureReviewServers.v1"]
    exposure: ReviewServer


class ReviewSources(ReviewModel):
    schema_version: Literal["exposureReviewSources.v1"]
    files: dict[str, str]
