"""
Copyright 2026 The Dapr Authors
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterator, List, Protocol, runtime_checkable

# This extension must import cleanly without pyspark installed (see AGENTS.md).
# Structural protocols describe exactly the pyspark.sql.Row / DataFrame surface
# we call, so callers get real static typing without a hard runtime dependency
# on pyspark, and tests can supply plain fakes instead of real Spark objects.


@runtime_checkable
class RowLike(Protocol):
    """The subset of ``pyspark.sql.Row`` this extension relies on.

    Deliberately excludes ``__contains__``: ``Row`` subclasses ``tuple``, so
    ``'x' in row`` tests membership among *values*, not field names — a
    well-known footgun. Field presence is always checked via ``asDict()``.
    """

    def asDict(self, recursive: bool = ...) -> Dict[str, Any]: ...

    def __getitem__(self, key: str) -> Any: ...


@runtime_checkable
class BatchDataFrameLike(Protocol):
    """The subset of ``pyspark.sql.DataFrame`` this extension relies on.

    ``limit``/``collect`` back the ``toLocalIterator`` fallback (see
    ``batch_handler._iter_rows``): some compute (observed on Databricks
    serverless / Spark Connect) raises on ``toLocalIterator`` itself
    ("not supported when using file-based collect"), so a bounded
    ``collect()`` is the fallback path, not an alternative primary path.
    """

    def toLocalIterator(self, prefetchPartitions: bool = ...) -> Iterator[RowLike]: ...

    def limit(self, num: int) -> 'BatchDataFrameLike': ...

    def collect(self) -> List[RowLike]: ...


RowMapper = Callable[[RowLike], Dict[str, Any]]
InstanceIdFactory = Callable[[RowLike, int], str]
