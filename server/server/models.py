import enum

from advanced_alchemy.base import BigIntAuditBase
from sqlalchemy import (
    Boolean,
    Enum,
    ForeignKey,
    Integer,
    Text,
    Uuid,
    func,
    Float,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncAttrs


class Base(BigIntAuditBase):
    """BigIntAuditBase adds id, created_at and updated_at columns."""

    __abstract__ = True


class Segment(Base):
    __tablename__ = "segments"
    __table_args__ = ()

    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("datasets.id"),
        nullable=False,
    )
    idx: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    src: Mapped[str] = mapped_column(Text, nullable=False)
    tgt: Mapped[str] = mapped_column(Text, nullable=True)  # optional reference

    dataset: Mapped["Dataset"] = relationship("Dataset", back_populates="segments")

    translations: Mapped[list["SegmentTranslation"]] = relationship(
        "SegmentTranslation",
        back_populates="segment",
        cascade="all, delete-orphan",
    )


class Dataset(Base):
    """A dataset is a collection of segments. If document level information
    becomes represent, we will represent it as an optional mapping in another
    table."""

    __tablename__ = "datasets"
    namespace_id: Mapped[int] = mapped_column(
        ForeignKey("namespaces.id"),
        nullable=False,
    )
    data_hash: Mapped[str] = mapped_column(Text, nullable=False, index=True)

    source_lang: Mapped[str] = mapped_column(Text, nullable=False)  # iso639-1 code
    target_lang: Mapped[str] = mapped_column(Text, nullable=False)  # iso639-1 code
    has_reference: Mapped[bool] = mapped_column(Boolean, nullable=False)

    names: Mapped[list["DatasetName"]] = relationship(
        "DatasetName",
        back_populates="dataset",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    namespace: Mapped["Namespace"] = relationship(
        "Namespace",
        back_populates="datasets",
    )
    segments: Mapped[list[Segment]] = relationship(
        "Segment",
        back_populates="dataset",
        cascade="all, delete-orphan",
        order_by="Segment.idx",
    )
    translation_runs: Mapped[list["TranslationRun"]] = relationship(
        "TranslationRun",
        back_populates="dataset",
        cascade="all, delete-orphan",
    )


class DatasetName(Base):
    __tablename__ = "dataset_names"
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("datasets.id"),
        primary_key=True,
    )
    dataset: Mapped[Dataset] = relationship(
        "Dataset",
        back_populates="names",
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)


# Translations


class SegmentTranslation(Base):
    __tablename__ = "segment_translations"
    tgt: Mapped[str] = mapped_column(Text, nullable=False)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("translation_runs.id"),
        nullable=False,
    )
    segment_id: Mapped[int] = mapped_column(
        ForeignKey("segments.id"),
        nullable=False,
    )
    segment: Mapped[Segment] = relationship(
        "Segment",
        back_populates="translations",
        lazy="selectin",
    )
    segment_idx: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )
    run: Mapped["TranslationRun"] = relationship(
        "TranslationRun",
        back_populates="translations",
    )

    segment_metrics: Mapped[list["SegmentMetric"]] = relationship(
        "SegmentMetric",
        back_populates="segment_translation",
        cascade="all, delete-orphan",
    )
    segment_ngrams: Mapped[list["SegmentTranslationNGrams"]] = relationship(
        "SegmentTranslationNGrams",
        back_populates="segment_translation",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class SegmentTranslationNGrams(Base):
    __tablename__ = "segment_translation_ngrams"
    run_id: Mapped[int] = mapped_column(
        ForeignKey("translation_runs.id"),
        nullable=False,
        index=True,
    )
    segment_translation_id: Mapped[int] = mapped_column(
        ForeignKey("segment_translations.id"),
        primary_key=True,
    )
    tokenizer: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    ngrams: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    ngrams_ref: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    n: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    segment_translation: Mapped[SegmentTranslation] = relationship(
        "SegmentTranslation",
        back_populates="segment_ngrams",
        lazy="selectin",
    )


class TranslationRun(Base):
    __tablename__ = "translation_runs"
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("datasets.id"),
        nullable=False,
    )
    namespace_id: Mapped[int] = mapped_column(
        ForeignKey("namespaces.id"),
        nullable=False,
    )
    uuid: Mapped[Uuid] = mapped_column(
        Uuid,
        nullable=False,
        default=func.uuid_generate_v4(),
        unique=True,
        index=True,
    )
    dataset: Mapped[Dataset] = relationship(
        "Dataset",
        back_populates="translation_runs",
        cascade="all",
    )
    translations: Mapped[list[SegmentTranslation]] = relationship(
        "SegmentTranslation",
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="SegmentTranslation.segment_idx",
    )
    segment_metrics: Mapped[list["SegmentMetric"]] = relationship(
        "SegmentMetric",
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="SegmentMetric.segment_idx",
    )
    dataset_metrics: Mapped[list["DatasetMetric"]] = relationship(
        "DatasetMetric",
        back_populates="run",
        cascade="all, delete-orphan",
    )
    generic_metrics: Mapped[list["GenericMetric"]] = relationship(
        "GenericMetric",
        back_populates="run",
        cascade="all, delete-orphan",
    )
    namespace: Mapped["Namespace"] = relationship(
        "Namespace",
    )
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


# Metric results
# TODO: add JSON payloads (used for fingerprints and any additional data)
# TODO: I should think through how to build efficient search index and FTS


class SegmentMetric(Base):
    __tablename__ = "segment_metrics"

    name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        index=True,
    )
    score: Mapped[float] = mapped_column(nullable=False)
    higher_is_better: Mapped[bool] = mapped_column(nullable=False)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("translation_runs.id"),
        nullable=False,
    )
    segment_translation_id: Mapped[int] = mapped_column(
        ForeignKey("segment_translations.id"),
        nullable=False,
    )
    segment_idx: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )
    run: Mapped[TranslationRun] = relationship(
        "TranslationRun",
        back_populates="segment_metrics",
    )
    segment_translation: Mapped[SegmentTranslation] = relationship(
        "SegmentTranslation",
        back_populates="segment_metrics",
    )


class DatasetMetric(Base):
    __tablename__ = "dataset_metrics"
    name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        index=True,
    )
    run_id: Mapped[int] = mapped_column(
        ForeignKey("translation_runs.id"),
        nullable=False,
    )

    score: Mapped[float] = mapped_column(nullable=False)
    higher_is_better: Mapped[bool] = mapped_column(nullable=False)

    run: Mapped["TranslationRun"] = relationship("TranslationRun")


class GenericMetric(Base):
    """ids, class + JSON payload only"""

    __tablename__ = "generic_metrics"
    run_id: Mapped[int] = mapped_column(
        ForeignKey("translation_runs.id"),
        nullable=False,
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    run: Mapped["TranslationRun"] = relationship("TranslationRun")


# auth


class Namespace(Base):
    """Users are global, everything else belongs to some namespace. User has either no-access/read-only/read-write access to each namespace. We plan no further granularity. Read-only access is meant to be used for public demos if any.

    Note that internally, we use integer IDs for namespaces, but to
    the user, we expose them as unique strings.
    """

    __tablename__ = "namespaces"

    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)

    datasets: Mapped[list[Dataset]] = relationship(
        "Dataset",
        back_populates="namespace",
        cascade="all, delete-orphan",
    )

    namespace_users: Mapped[list["NamespaceUser"]] = relationship(
        "NamespaceUser",
        back_populates="namespace",
        cascade="all, delete-orphan",
    )

    users: Mapped[list["User"]] = relationship(
        "User",
        secondary="namespace_users",
        back_populates="namespaces",
        viewonly=True,
    )


class NamespaceUser(Base):
    """Association table for the many-to-many relationship between users and namespaces"""

    __tablename__ = "namespace_users"

    namespace_id: Mapped[int] = mapped_column(
        ForeignKey("namespaces.id"),
        primary_key=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        primary_key=True,
    )
    can_write: Mapped[bool] = mapped_column(nullable=False, default=False)

    namespace: Mapped["Namespace"] = relationship(
        "Namespace",
        back_populates="namespace_users",
    )
    user: Mapped["User"] = relationship(
        "User",
        back_populates="namespace_users",
    )


class User(Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)

    namespaces: Mapped[list["Namespace"]] = relationship(
        "Namespace",
        secondary="namespace_users",
        back_populates="users",
        viewonly=True,
    )

    namespace_users: Mapped[list["NamespaceUser"]] = relationship(
        "NamespaceUser",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class WorkerStatus(enum.Enum):
    WAITING = 1
    WORKING = 2
    FINISHED = 3
    TIMED_OUT = 4  # Worker did not explicitly finish, but stopped sending heartbeats


class Worker(Base):
    __tablename__ = "workers"

    namespace_id: Mapped[int] = mapped_column(
        ForeignKey("namespaces.id"),
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )
    status: Mapped[WorkerStatus] = mapped_column(
        Enum(WorkerStatus, name="worker_status_enum"),
        nullable=False,
    )
    last_heartbeat: Mapped[float] = mapped_column(
        Float, nullable=False, default=0
    )  # Unix timestamp in seconds
    metric: Mapped[str] = mapped_column(
        # This string should uniquely identify the type of the metric
        Text,
        nullable=False,
        index=True,
    )
    metric_requires_references: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    queue: Mapped[str] = mapped_column(Text, nullable=False, index=True)

    user: Mapped["User"] = relationship(
        "User",
    )
    namespace: Mapped["Namespace"] = relationship(
        "Namespace",
    )


class JobStatus(enum.Enum):
    PENDING = 1
    RUNNING = 2
    COMPLETED = 3


class Job(Base):
    __tablename__ = "jobs"

    namespace_id: Mapped[int] = mapped_column(
        ForeignKey("namespaces.id"),
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )
    run_id: Mapped[int] = mapped_column(
        ForeignKey("translation_runs.id"),
        nullable=False,
    )
    worker_id: Mapped[int] = mapped_column(
        ForeignKey("workers.id"),
        nullable=True,  # Nullable if the job is not yet assigned to a worker
    )

    queue: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus), nullable=False, index=True
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    metric: Mapped[str] = mapped_column(
        # This string should uniquely identify the type of the metric
        Text,
        nullable=False,
        index=True,
    )

    namespace: Mapped["Namespace"] = relationship(
        "Namespace",
    )
    user: Mapped["User"] = relationship(
        "User",
    )
    run: Mapped["TranslationRun"] = relationship(
        "TranslationRun",
    )
