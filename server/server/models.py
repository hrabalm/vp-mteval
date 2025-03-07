from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from litestar import Litestar, get, post, put
from litestar.contrib.sqlalchemy.plugins import SQLAlchemyAsyncConfig, SQLAlchemyPlugin
from litestar.exceptions import ClientException, NotFoundException
from litestar.status_codes import HTTP_409_CONFLICT


class Base(DeclarativeBase): ...


class TodoItem(Base):
    __tablename__ = "todo_items"

    title: Mapped[str] = mapped_column(primary_key=True)
    done: Mapped[bool]


# TODO:
# - How do I store mnetrics data?:
#   - Sentence level / Document level / special (n-grams)
#   - I need a mechanism to store arbitrary JSON data for all segments, documents or datasets
#   - Add creation date and last update date to Base?

# Documents


class Segment(Base):
    __tablename__ = "segments"

    src: Mapped[str]
    tgt: Mapped[str]


class Document(Base):
    __tablename__ = "documents"

    segments: list[Segment]


class Dataset(Base):
    __tablename__ = "datasets"

    documents: list[Document]
    languages: Mapped[str]
    # namespace:


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
    pass


class DocumentMetric(Base):
    __tablename__ = "document_metrics"
    pass


class DatasetMetric(Base):
    __tablename__ = "dataset_metrics"


class GenericMetric(Base):
    """ids, class + JSON payload only"""

    __tablename__ = "generic_metrics"


# auth


class Namespace(Base):
    """Users are global, everything else belongs to some namespace. User has either no-access/read-only/read-write access to each namespace. We plan no further granularity. Read-only access is meant to be used for public demos if any."""

    __tablename__ = "namespaces"

    name: Mapped[str] = mapped_column(primary_key=True)


class User(Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(primary_key=True)
    # email:
    # password:


# TODO: jobs
# - we need to support queues (CPU and GPU)
# - we might want to support priorities - low/default/high
# - user and namespace (so that the job runner can choose to filter jobs by it)


class Job(Base):
    __tablename__ = "jobs"
