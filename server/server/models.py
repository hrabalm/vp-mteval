from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    __abstract__ = True
    creation_date: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    last_update_date: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class TodoItem(Base):
    __tablename__ = "todo_items"

    title: Mapped[str] = mapped_column(primary_key=True)
    done: Mapped[bool] = mapped_column(nullable=False)


# TODO:
# - How do I store metrics data?:
#   - Sentence level / Document level / special (n-grams)
#   - I need a mechanism to store arbitrary JSON data for all segments, documents or datasets
#   - Add creation date and last update date to Base?

# Documents


class Segment(Base):
    __tablename__ = "segments"
    __table_args__ = ()

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("datasets.id"), ondelete="CASCADE", nullable=False
    )
    src: Mapped[str] = mapped_column(Text, nullable=False)
    tgt: Mapped[str] = mapped_column(Text, nullable=False)


class Dataset(Base):
    """A dataset is a collection of segments. If document level information
    becomes represent, we will represent it as an optional mapping in another
    table."""

    __tablename__ = "datasets"
    id = mapped_column(primary_key=True)
    namespace_id: Mapped[int] = mapped_column(
        ForeignKey("namespaces.id"), ondelete="CASCADE", nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    data_hash: Mapped[str] = mapped_column(Text, nullable=False)

    source_lang: Mapped[str] = mapped_column(Text, nullable=False)  # iso639-1 code
    target_lang: Mapped[str] = mapped_column(Text, nullable=False)  # iso639-1 code

    segments: Mapped[list[Segment]] = relationship(
        "Segment",
        back_populates="dataset",
        cascade="all, delete-orphan",
    )


# Translations


class SegmentTranslation(Base):
    __tablename__ = "segment_translations"


class TranslationRun(Base):
    __tablename__ = "translation_runs"


# Metric results
# TODO: add JSON payloads (used for fingerprints and any additional data)
# TODO: I should think through how to build efficient search index and FTS


class SegmentMetric(Base):
    __tablename__ = "segment_metrics"

    score: Mapped[float] = mapped_column(nullable=False)
    higher_is_better: Mapped[bool] = mapped_column(nullable=False)
    segment_id: Mapped[int] = mapped_column(
        ForeignKey("segments.id"), ondelete="CASCADE", nullable=False
    )
    segment: Mapped[Segment] = relationship(
        "Segment",
        back_populates="metrics",
        cascade="all, delete-orphan",
    )


class DatasetMetric(Base):
    __tablename__ = "dataset_metrics"


class GenericMetric(Base):
    """ids, class + JSON payload only"""

    __tablename__ = "generic_metrics"


# auth


class Namespace(Base):
    """Users are global, everything else belongs to some namespace. User has either no-access/read-only/read-write access to each namespace. We plan no further granularity. Read-only access is meant to be used for public demos if any."""

    __tablename__ = "namespaces"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)

    # TODO: add many to many relationship to users with R or R/W access


class User(Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)


# TODO: jobs
# - we need to support queues (at least CPU and GPU)
# - we might want to support priorities - low/default/high
# - user and namespace (so that the job runner can choose to filter jobs by it)


class Job(Base):
    __tablename__ = "jobs"
