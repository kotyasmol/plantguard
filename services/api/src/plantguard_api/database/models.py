from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    MetaData,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Plant(CreatedAtMixin, Base):
    __tablename__ = "plants"
    __table_args__ = (
        CheckConstraint(
            "species_status IN ('unconfirmed', 'suggested', 'confirmed')",
            name="ck_plants_species_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    nickname: Mapped[str] = mapped_column(String(100), nullable=False)
    species_scientific_name: Mapped[Optional[str]] = mapped_column(String(160))
    species_common_name: Mapped[Optional[str]] = mapped_column(String(160))
    species_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unconfirmed", server_default="unconfirmed"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    observations: Mapped[list[Observation]] = relationship(
        back_populates="plant", cascade="all, delete-orphan", passive_deletes=True
    )
    care_events: Mapped[list[CareEvent]] = relationship(
        back_populates="plant", cascade="all, delete-orphan", passive_deletes=True
    )


class Observation(CreatedAtMixin, Base):
    __tablename__ = "observations"
    __table_args__ = (
        CheckConstraint(
            "humidity_pct IS NULL OR humidity_pct BETWEEN 0 AND 100",
            name="ck_observations_humidity_range",
        ),
        CheckConstraint(
            "temperature_c IS NULL OR temperature_c BETWEEN -50 AND 70",
            name="ck_observations_temperature_range",
        ),
        Index("ix_observations_plant_observed_at", "plant_id", "observed_at"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    plant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("plants.id", ondelete="CASCADE"), nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(Text)
    humidity_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    temperature_c: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    plant: Mapped[Plant] = relationship(back_populates="observations")
    photos: Mapped[list[Photo]] = relationship(
        back_populates="observation", cascade="all, delete-orphan", passive_deletes=True
    )
    assessments: Mapped[list[Assessment]] = relationship(
        back_populates="observation",
        cascade="all, delete-orphan",
        foreign_keys="Assessment.observation_id",
        passive_deletes=True,
    )


class Photo(CreatedAtMixin, Base):
    __tablename__ = "photos"
    __table_args__ = (
        CheckConstraint("size_bytes > 0", name="ck_photos_size_positive"),
        CheckConstraint("length(checksum_sha256) = 64", name="ck_photos_checksum_length"),
        UniqueConstraint("storage_key", name="uq_photos_storage_key"),
        Index("ix_photos_observation_id", "observation_id"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    observation_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("observations.id", ondelete="CASCADE"), nullable=False
    )
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    media_type: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    observation: Mapped[Observation] = relationship(back_populates="photos")


class CareEvent(CreatedAtMixin, Base):
    __tablename__ = "care_events"
    __table_args__ = (
        CheckConstraint(
            "action_type IN ('watered', 'fertilized', 'repotted', 'moved', 'pruned', "
            "'treated', 'other')",
            name="ck_care_events_action_type",
        ),
        Index("ix_care_events_plant_performed_at", "plant_id", "performed_at"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    plant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("plants.id", ondelete="CASCADE"), nullable=False
    )
    action_type: Mapped[str] = mapped_column(String(24), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    performed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    plant: Mapped[Plant] = relationship(back_populates="care_events")


class Assessment(CreatedAtMixin, Base):
    __tablename__ = "assessments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'succeeded', 'needs_review', 'failed')",
            name="ck_assessments_status",
        ),
        CheckConstraint(
            "risk_level IN ('unknown', 'low', 'medium', 'high')",
            name="ck_assessments_risk_level",
        ),
        CheckConstraint(
            "identification_confidence IS NULL OR identification_confidence BETWEEN 0 AND 1",
            name="ck_assessments_identification_confidence",
        ),
        CheckConstraint(
            "finding_confidence IS NULL OR finding_confidence BETWEEN 0 AND 1",
            name="ck_assessments_finding_confidence",
        ),
        Index("ix_assessments_observation_created_at", "observation_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    observation_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("observations.id", ondelete="CASCADE"), nullable=False
    )
    previous_assessment_id: Mapped[Optional[UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("assessments.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="pending", server_default="pending"
    )
    identified_scientific_name: Mapped[Optional[str]] = mapped_column(String(160))
    identification_confidence: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))
    finding_code: Mapped[Optional[str]] = mapped_column(String(80))
    finding_confidence: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))
    risk_level: Mapped[str] = mapped_column(
        String(16), nullable=False, default="unknown", server_default="unknown"
    )
    explanation: Mapped[Optional[str]] = mapped_column(Text)
    model_version: Mapped[Optional[str]] = mapped_column(String(120))

    observation: Mapped[Observation] = relationship(
        back_populates="assessments", foreign_keys=[observation_id]
    )
    previous_assessment: Mapped[Optional[Assessment]] = relationship(
        remote_side=[id], foreign_keys=[previous_assessment_id]
    )
