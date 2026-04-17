"""Pydantic schemas for CVs and portfolios (Phase 19)."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Section content
# ---------------------------------------------------------------------------


class Contact(BaseModel):
    full_name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    website: str = ""
    linkedin: str = ""
    github: str = ""


class ExperienceEntry(BaseModel):
    company: str = ""
    title: str = ""
    start: str = ""
    end: str = ""
    location: str = ""
    bullets: list[str] = Field(default_factory=list)


class EducationEntry(BaseModel):
    school: str = ""
    degree: str = ""
    field: str = ""
    start: str = ""
    end: str = ""
    gpa: str = ""


class ProjectEntry(BaseModel):
    name: str = ""
    url: str = ""
    description: str = ""
    tech: list[str] = Field(default_factory=list)


class CertificationEntry(BaseModel):
    name: str = ""
    issuer: str = ""
    date: str = ""


class LanguageEntry(BaseModel):
    name: str = ""
    level: str = ""


class CustomSection(BaseModel):
    heading: str = ""
    body_markdown: str = ""


class CVSections(BaseModel):
    contact: Contact = Field(default_factory=Contact)
    summary: str = ""
    experience: list[ExperienceEntry] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    projects: list[ProjectEntry] = Field(default_factory=list)
    certifications: list[CertificationEntry] = Field(default_factory=list)
    languages: list[LanguageEntry] = Field(default_factory=list)
    custom: list[CustomSection] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# API I/O
# ---------------------------------------------------------------------------


class CVCreate(BaseModel):
    title: str
    kind: str = "cv"  # "cv" or "portfolio"
    template: str = "minimal"
    sections: CVSections | None = None
    is_default: bool = False


class CVUpdate(BaseModel):
    title: str | None = None
    kind: str | None = None
    template: str | None = None
    sections: CVSections | None = None
    is_default: bool | None = None


class CVOut(BaseModel):
    id: str
    title: str
    kind: str
    template: str
    sections: CVSections
    source_file: str = ""
    pdf_file: str = ""
    tailored_from_cv_id: str | None = None
    tailored_for_job_id: int | None = None
    is_default: bool = False
    created_at: str | None = None
    updated_at: str | None = None


class CVTailorRequest(BaseModel):
    job_id: int
    new_title: str | None = None


class CVExportResponse(BaseModel):
    id: str
    pdf_file: str
    download_url: str


class CVListResponse(BaseModel):
    cvs: list[CVOut]
    total: int
