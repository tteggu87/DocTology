from __future__ import annotations

import builtins
import argparse
import hashlib
import importlib.util
import io
import json
import sqlite3
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP_PATH = (
    ROOT
    / ".agents"
    / "skills"
    / "llm-wiki-bootstrap"
    / "scripts"
    / "bootstrap_llm_wiki.py"
)


def load_module(name: str, path: Path):
    if path.name == "wiki_retrieval.py":
        sys.modules.pop("reindex_sqlite_operational", None)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeEmbedder:
    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            if "Alpha" in text:
                vectors.append([3.0, 0.0])
            elif "Beta" in text:
                vectors.append([0.0, 2.0])
            else:
                vectors.append([-1.0, 0.0])
        return vectors


class RecordingFakeEmbedder(FakeEmbedder):
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return super().embed(texts)


class RefreshFakeProvider(RecordingFakeEmbedder):
    model_identity = "fake-model-v1"
    tokenizer_identity = "fake-tokenizer-v1"
    preprocessing_identity = "fake-preprocessing-v1"


class FakeEncoding:
    def __init__(self, width: int) -> None:
        self.ids = list(range(width))
        self.attention_mask = [1] * width
        self.type_ids = [0] * width


class RecordingTokenizer:
    def __init__(self, maximum: int) -> None:
        self.maximum = maximum
        self.batch_sizes: list[int] = []

    def encode_batch(self, texts: list[str]) -> list[FakeEncoding]:
        self.batch_sizes.append(len(texts))
        return [FakeEncoding(min(len(text), self.maximum)) for text in texts]


class FakeInput:
    def __init__(self, name: str) -> None:
        self.name = name


class RecordingSession:
    def __init__(self) -> None:
        self.input_shapes: list[tuple[int, int]] = []

    def get_inputs(self) -> list[FakeInput]:
        return [FakeInput("input_ids"), FakeInput("attention_mask")]

    def run(self, _outputs, feed):
        batch, width = feed["input_ids"].shape
        self.input_shapes.append((batch, width))
        return [FakeOutput(batch, width, 2)]


class FakeArray:
    def __init__(self, rows: list[list[int]]) -> None:
        self.rows = rows
        self.shape = (len(rows), len(rows[0]) if rows else 0)


class FakeNumpy:
    int64 = "int64"

    @staticmethod
    def asarray(rows: list[list[int]], *, dtype: str) -> FakeArray:
        if dtype != FakeNumpy.int64:
            raise TypeError(f"unexpected dtype: {dtype}")
        return FakeArray(rows)


class FakeOutput:
    ndim = 3

    def __init__(self, batch: int, width: int, dimensions: int) -> None:
        self.shape = (batch, width, dimensions)

    def tolist(self) -> list[list[list[float]]]:
        batch, width, dimensions = self.shape
        return [[[1.0] * dimensions for _ in range(width)] for _ in range(batch)]


class WikiSqliteSemanticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bootstrap = load_module("bootstrap_for_semantic_test", BOOTSTRAP_PATH)

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name) / "vault"
        self.bootstrap.scaffold(self.root, force=False, profile="wiki-only")
        concepts = self.root / "wiki" / "concepts"
        (concepts / "alpha.md").write_text("# Alpha\nVector one.\n", encoding="utf-8")
        (concepts / "beta.md").write_text("# Beta\nVector two.\n", encoding="utf-8")
        self.run_cli("rebuild")
        sys.path.insert(0, str(self.root / "scripts"))
        self.addCleanup(lambda: sys.path.remove(str(self.root / "scripts")))
        self.retrieval = load_module(
            f"wiki_retrieval_semantic_test_{id(self)}",
            self.root / "scripts" / "wiki_retrieval.py",
        )

    def run_cli(
        self, *arguments: str, expected_returncode: int = 0
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [
                sys.executable,
                str(self.root / "scripts" / "wiki_retrieval.py"),
                "--repo-root",
                str(self.root),
                *arguments,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, expected_returncode, result.stderr)
        return result

    def persist_fake_embeddings(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.root / "state" / "wiki_index.sqlite")
        connection.row_factory = sqlite3.Row
        result = self.retrieval.persist_embeddings(
            connection, FakeEmbedder(), "fake-model-v1", "fake-tokenizer-v1"
        )
        self.assertEqual(result["dimensions"], 2)
        self.assertEqual(
            result["embedded_chunks"] + result["reused_chunks"],
            2,
        )
        return connection

    def test_embedding_persistence_binds_identity_hash_dimensions_and_fingerprint(
        self,
    ) -> None:
        with self.persist_fake_embeddings() as connection:
            rows = connection.execute(
                """
                SELECT e.*, c.content_hash current_hash
                FROM chunk_embeddings e JOIN chunks c ON c.id = e.chunk_id
                ORDER BY e.chunk_id
                """
            ).fetchall()
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertEqual(row["chunk_hash"], row["current_hash"])
            self.assertEqual(row["model_identity"], "fake-model-v1")
            self.assertEqual(row["tokenizer_identity"], "fake-tokenizer-v1")
            self.assertEqual(
                row["preprocessing_identity"],
                self.retrieval.DEFAULT_PREPROCESSING_IDENTITY,
            )
            self.assertEqual(row["dimensions"], 2)
            self.assertEqual(
                row["vector_fingerprint"], hashlib.sha256(row["vector"]).hexdigest()
            )

    def test_embedding_persistence_streams_missing_chunks_in_bounded_batches(
        self,
    ) -> None:
        concepts = self.root / "wiki" / "concepts"
        for index in range(129):
            (concepts / f"bulk-{index}.md").write_text(
                f"# Bulk {index}\nVector payload {index}.\n", encoding="utf-8"
            )
        self.run_cli("rebuild")
        connection = sqlite3.connect(self.root / "state" / "wiki_index.sqlite")
        connection.row_factory = sqlite3.Row
        self.addCleanup(connection.close)
        embedder = RecordingFakeEmbedder()
        result = self.retrieval.persist_embeddings(
            connection, embedder, "fake-model-v1", "fake-tokenizer-v1"
        )

        expected = 131
        self.assertEqual(result["embedded_chunks"], expected)
        self.assertEqual(result["reused_chunks"], 0)
        self.assertEqual([len(batch) for batch in embedder.calls], [128, 3])
        self.assertEqual(
            connection.execute("SELECT count(*) FROM chunk_embeddings").fetchone()[0],
            expected,
        )

    def test_rebuild_reuses_only_current_structurally_valid_vectors(self) -> None:
        with self.persist_fake_embeddings():
            pass

        self.run_cli("rebuild")
        with sqlite3.connect(self.root / "state" / "wiki_index.sqlite") as connection:
            self.assertEqual(
                connection.execute("SELECT count(*) FROM chunk_embeddings").fetchone()[
                    0
                ],
                2,
            )

        alpha = self.root / "wiki" / "concepts" / "alpha.md"
        alpha.write_text("# Alpha\nVector one changed.\n", encoding="utf-8")
        self.run_cli("rebuild")
        with sqlite3.connect(self.root / "state" / "wiki_index.sqlite") as connection:
            carried = connection.execute(
                """
                SELECT p.title
                FROM chunk_embeddings e
                JOIN chunks c ON c.id = e.chunk_id
                JOIN documents d ON d.id = c.document_id
                JOIN pages p ON p.id = d.page_id
                """
            ).fetchall()
        self.assertEqual(carried, [("Beta",)])

        connection = sqlite3.connect(self.root / "state" / "wiki_index.sqlite")
        connection.row_factory = sqlite3.Row
        embedder = RecordingFakeEmbedder()
        result = self.retrieval.persist_embeddings(
            connection, embedder, "fake-model-v1", "fake-tokenizer-v1"
        )
        connection.close()
        self.assertEqual(result["reused_chunks"], 1)
        self.assertEqual(result["embedded_chunks"], 1)
        self.assertEqual(len(embedder.calls), 1)
        self.assertEqual(len(embedder.calls[0]), 1)
        self.assertIn("changed", embedder.calls[0][0])

        (self.root / "wiki" / "concepts" / "beta.md").unlink()
        self.run_cli("rebuild")
        with sqlite3.connect(self.root / "state" / "wiki_index.sqlite") as connection:
            self.assertEqual(
                connection.execute("SELECT count(*) FROM chunk_embeddings").fetchone()[
                    0
                ],
                1,
            )
            connection.execute(
                "UPDATE chunk_embeddings SET vector_fingerprint = 'corrupt'"
            )
            connection.commit()
        self.run_cli("rebuild")
        with sqlite3.connect(self.root / "state" / "wiki_index.sqlite") as connection:
            self.assertEqual(
                connection.execute("SELECT count(*) FROM chunk_embeddings").fetchone()[
                    0
                ],
                0,
            )

    def test_embedding_identity_change_never_reuses_prior_model_vectors(self) -> None:
        with self.persist_fake_embeddings():
            pass
        self.run_cli("rebuild")
        connection = sqlite3.connect(self.root / "state" / "wiki_index.sqlite")
        connection.row_factory = sqlite3.Row
        embedder = RecordingFakeEmbedder()

        result = self.retrieval.persist_embeddings(
            connection, embedder, "fake-model-v2", "fake-tokenizer-v1"
        )

        self.assertEqual(result["reused_chunks"], 0)
        self.assertEqual(result["embedded_chunks"], 2)
        self.assertEqual(len(embedder.calls[0]), 2)
        self.assertEqual(
            connection.execute(
                "SELECT count(*) FROM chunk_embeddings WHERE model_identity = ?",
                ("fake-model-v2",),
            ).fetchone()[0],
            2,
        )
        self.assertEqual(
            connection.execute("SELECT count(*) FROM chunk_embeddings").fetchone()[0],
            2,
        )
        self.assertEqual(
            [
                row[0]
                for row in connection.execute(
                    "SELECT DISTINCT model_identity FROM chunk_embeddings"
                )
            ],
            ["fake-model-v2"],
        )
        connection.close()

    def test_rebuild_rejects_inconsistent_cohort_dimensions(self) -> None:
        with self.persist_fake_embeddings() as connection:
            row = connection.execute(
                "SELECT rowid, vector FROM chunk_embeddings ORDER BY rowid LIMIT 1"
            ).fetchone()
            shortened = bytes(row["vector"])[:4]
            connection.execute(
                """
                UPDATE chunk_embeddings
                SET dimensions = 1, vector = ?, vector_fingerprint = ?
                WHERE rowid = ?
                """,
                (shortened, hashlib.sha256(shortened).hexdigest(), row["rowid"]),
            )
            connection.commit()

        self.run_cli("rebuild")

        with sqlite3.connect(self.root / "state" / "wiki_index.sqlite") as connection:
            self.assertEqual(
                connection.execute("SELECT count(*) FROM chunk_embeddings").fetchone()[
                    0
                ],
                0,
            )

    def test_carry_forward_failure_preserves_prior_readable_index(self) -> None:
        with self.persist_fake_embeddings():
            pass
        database = self.root / "state" / "wiki_index.sqlite"

        with (
            mock.patch.object(
                self.retrieval.indexer,
                "carry_forward_embeddings",
                side_effect=sqlite3.DatabaseError("carry failed"),
            ),
            self.assertRaises(sqlite3.DatabaseError),
        ):
            self.retrieval.indexer.rebuild(
                self.root, self.retrieval.indexer.DEFAULT_CHUNK_THRESHOLD
            )

        with sqlite3.connect(database) as connection:
            self.assertEqual(
                connection.execute("SELECT count(*) FROM chunk_embeddings").fetchone()[
                    0
                ],
                2,
            )
            self.assertEqual(
                connection.execute("PRAGMA quick_check").fetchone()[0], "ok"
            )

    def test_internal_carry_forward_read_error_preserves_prior_index(self) -> None:
        with self.persist_fake_embeddings():
            pass
        database = self.root / "state" / "wiki_index.sqlite"
        original_connect = sqlite3.connect

        def fail_read_only_connect(database_name, *args, **kwargs):
            if str(database_name).startswith("file:") and kwargs.get("uri"):
                raise sqlite3.DatabaseError("internal carry read failed")
            return original_connect(database_name, *args, **kwargs)

        with (
            mock.patch.object(
                self.retrieval.indexer.sqlite3,
                "connect",
                side_effect=fail_read_only_connect,
            ),
            self.assertRaisesRegex(sqlite3.DatabaseError, "internal carry read failed"),
        ):
            self.retrieval.indexer.rebuild(
                self.root, self.retrieval.indexer.DEFAULT_CHUNK_THRESHOLD
            )

        with sqlite3.connect(database) as connection:
            self.assertEqual(
                connection.execute("SELECT count(*) FROM chunk_embeddings").fetchone()[
                    0
                ],
                2,
            )
            self.assertEqual(
                connection.execute("PRAGMA quick_check").fetchone()[0], "ok"
            )

    def test_internal_carry_forward_os_error_preserves_prior_index(self) -> None:
        with self.persist_fake_embeddings():
            pass
        database = self.root / "state" / "wiki_index.sqlite"
        original_open = Path.open

        def fail_existing_index_read(path, *args, **kwargs):
            mode = args[0] if args else kwargs.get("mode", "r")
            if path == database and mode == "rb":
                raise OSError("internal carry file read failed")
            return original_open(path, *args, **kwargs)

        with (
            mock.patch.object(
                Path,
                "open",
                autospec=True,
                side_effect=fail_existing_index_read,
            ),
            self.assertRaisesRegex(OSError, "internal carry file read failed"),
        ):
            self.retrieval.indexer.rebuild(
                self.root, self.retrieval.indexer.DEFAULT_CHUNK_THRESHOLD
            )

        with sqlite3.connect(database) as connection:
            self.assertEqual(
                connection.execute("SELECT count(*) FROM chunk_embeddings").fetchone()[
                    0
                ],
                2,
            )
            self.assertEqual(
                connection.execute("PRAGMA quick_check").fetchone()[0], "ok"
            )

    def test_non_finite_vectors_are_never_reused_or_served(self) -> None:
        with self.persist_fake_embeddings() as connection:
            rowid = connection.execute(
                "SELECT rowid FROM chunk_embeddings ORDER BY rowid LIMIT 1"
            ).fetchone()[0]
            invalid = struct.pack("<2f", float("nan"), 0.0)
            connection.execute(
                """
                UPDATE chunk_embeddings
                SET vector = ?, vector_fingerprint = ?
                WHERE rowid = ?
                """,
                (invalid, hashlib.sha256(invalid).hexdigest(), rowid),
            )
            connection.execute(
                """
                UPDATE index_metadata SET value = ?
                WHERE key = 'semantic_cohort_fingerprint'
                """,
                (self.retrieval.indexer.semantic_cohort_fingerprint(connection),),
            )
            connection.commit()

            with self.assertRaisesRegex(
                self.retrieval.SemanticLaneUnavailable, "finite values"
            ):
                self.retrieval.semantic_rows(
                    connection,
                    [1.0, 0.0],
                    "fake-model-v1",
                    "fake-tokenizer-v1",
                    10,
                )

        status = json.loads(self.run_cli("status").stdout)
        self.assertEqual(status["semantic_lane"], "unavailable")
        self.assertIn("vector_values", status["semantic_reasons"])
        doctor = json.loads(self.run_cli("doctor", expected_returncode=1).stdout)
        self.assertIn("vector_values", doctor["stale_reasons"])

        connection = sqlite3.connect(self.root / "state" / "wiki_index.sqlite")
        connection.row_factory = sqlite3.Row
        embedder = RecordingFakeEmbedder()
        result = self.retrieval.persist_embeddings(
            connection, embedder, "fake-model-v1", "fake-tokenizer-v1"
        )
        connection.close()
        self.assertEqual(result["reused_chunks"], 1)
        self.assertEqual(result["embedded_chunks"], 1)

        with self.persist_fake_embeddings() as connection:
            rowid = connection.execute(
                "SELECT rowid FROM chunk_embeddings ORDER BY rowid LIMIT 1"
            ).fetchone()[0]
            invalid = struct.pack("<2f", float("inf"), 0.0)
            connection.execute(
                """
                UPDATE chunk_embeddings
                SET vector = ?, vector_fingerprint = ?
                WHERE rowid = ?
                """,
                (invalid, hashlib.sha256(invalid).hexdigest(), rowid),
            )
            connection.commit()
        self.run_cli("rebuild")
        with sqlite3.connect(self.root / "state" / "wiki_index.sqlite") as connection:
            self.assertEqual(
                connection.execute("SELECT count(*) FROM chunk_embeddings").fetchone()[
                    0
                ],
                1,
            )

    def test_zero_vectors_are_never_attested_reused_or_served(self) -> None:
        with self.persist_fake_embeddings() as connection:
            rowid = connection.execute(
                "SELECT rowid FROM chunk_embeddings ORDER BY rowid LIMIT 1"
            ).fetchone()[0]
            zero = struct.pack("<2f", 0.0, 0.0)
            connection.execute(
                """
                UPDATE chunk_embeddings
                SET vector = ?, vector_fingerprint = ?
                WHERE rowid = ?
                """,
                (zero, hashlib.sha256(zero).hexdigest(), rowid),
            )
            connection.execute(
                """
                UPDATE index_metadata SET value = ?
                WHERE key = 'semantic_cohort_fingerprint'
                """,
                (self.retrieval.indexer.semantic_cohort_fingerprint(connection),),
            )
            connection.commit()

            with self.assertRaisesRegex(
                self.retrieval.SemanticLaneUnavailable, "non-zero magnitude"
            ):
                self.retrieval.semantic_rows(
                    connection,
                    [1.0, 0.0],
                    "fake-model-v1",
                    "fake-tokenizer-v1",
                    10,
                )
            with self.assertRaisesRegex(
                self.retrieval.indexer.RebuildError, "finite non-zero vectors"
            ):
                self.retrieval.indexer.attest_semantic_vectors(connection)

        status = json.loads(self.run_cli("status").stdout)
        self.assertEqual(status["semantic_lane"], "unavailable")
        self.assertIn("vector_values", status["semantic_reasons"])
        doctor = json.loads(self.run_cli("doctor", expected_returncode=1).stdout)
        self.assertIn("vector_values", doctor["stale_reasons"])

        connection = sqlite3.connect(self.root / "state" / "wiki_index.sqlite")
        connection.row_factory = sqlite3.Row
        result = self.retrieval.persist_embeddings(
            connection,
            RecordingFakeEmbedder(),
            "fake-model-v1",
            "fake-tokenizer-v1",
        )
        connection.close()
        self.assertEqual(result["reused_chunks"], 1)
        self.assertEqual(result["embedded_chunks"], 1)

        with self.persist_fake_embeddings() as connection:
            rowid = connection.execute(
                "SELECT rowid FROM chunk_embeddings ORDER BY rowid LIMIT 1"
            ).fetchone()[0]
            connection.execute(
                """
                UPDATE chunk_embeddings
                SET vector = ?, vector_fingerprint = ?
                WHERE rowid = ?
                """,
                (zero, hashlib.sha256(zero).hexdigest(), rowid),
            )
            connection.commit()
        self.run_cli("rebuild")
        with sqlite3.connect(self.root / "state" / "wiki_index.sqlite") as connection:
            self.assertEqual(
                connection.execute("SELECT count(*) FROM chunk_embeddings").fetchone()[
                    0
                ],
                1,
            )

    def test_exact_cosine_order_excludes_stale_vectors_and_dimension_mismatch(
        self,
    ) -> None:
        with self.persist_fake_embeddings() as connection:
            ordered = self.retrieval.semantic_rows(
                connection, [1.0, 0.0], "fake-model-v1", "fake-tokenizer-v1", 10
            )
            self.assertEqual(ordered[0]["title"], "Alpha")
            self.assertTrue(ordered[0]["node_id"].startswith("structure-node-"))
            self.assertGreater(
                ordered[0]["semantic_score"], ordered[1]["semantic_score"]
            )

            connection.execute(
                "UPDATE chunk_embeddings SET chunk_hash = 'stale' WHERE chunk_id = ?",
                (ordered[0]["chunk_id"],),
            )
            connection.commit()
            with self.assertRaises(self.retrieval.SemanticLaneUnavailable):
                self.retrieval.semantic_rows(
                    connection,
                    [1.0, 0.0],
                    "fake-model-v1",
                    "fake-tokenizer-v1",
                    10,
                )
            with self.assertRaises(self.retrieval.SemanticLaneUnavailable):
                self.retrieval.semantic_rows(
                    connection,
                    [1.0, 0.0, 0.0],
                    "fake-model-v1",
                    "fake-tokenizer-v1",
                    10,
                )

    def test_provider_is_lazy_and_missing_optional_runtime_is_graceful(self) -> None:
        model = self.root / "model.onnx"
        tokenizer = self.root / "tokenizer.json"
        model.write_bytes(b"model")
        tokenizer.write_text("{}", encoding="utf-8")
        provider = self.retrieval.OnnxSemanticProvider(model, tokenizer)

        real_import = builtins.__import__

        def guarded_import(name, *args, **kwargs):
            if name == "onnxruntime":
                raise ImportError("not installed for test")
            return real_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=guarded_import):
            self.assertIn(hashlib.sha256(b"model").hexdigest(), provider.model_identity)
            with self.assertRaises(self.retrieval.SemanticLaneUnavailable):
                provider.embed(["query"])

        unavailable = self.run_cli("semantic", "query", expected_returncode=1)
        self.assertEqual(json.loads(unavailable.stdout)["semantic_lane"], "unavailable")
        lexical = self.run_cli("search", "Alpha", "--hops", "0")
        self.assertEqual(json.loads(lexical.stdout)["results"][0]["title"], "Alpha")

        both = self.run_cli("search", "Alpha", "--mode", "both", "--hops", "0")
        payload = json.loads(both.stdout)
        self.assertEqual(payload["semantic_lane"], "unavailable")
        self.assertEqual(payload["lanes"]["lexical"]["anchors"][0]["title"], "Alpha")
        self.assertEqual(payload["lanes"]["semantic"]["anchors"], [])
        self.assertIn("reason", payload["lanes"]["semantic"])

    def test_standalone_semantic_checks_current_markdown_before_provider(self) -> None:
        alpha = self.root / "wiki" / "concepts" / "alpha.md"
        alpha.write_text("# Alpha\nStale vector source.\n", encoding="utf-8")
        args = argparse.Namespace(query="query", limit=10)
        with (
            mock.patch.object(
                self.retrieval,
                "semantic_provider",
                side_effect=AssertionError("stale semantic search must not load ONNX"),
            ),
            self.assertRaisesRegex(self.retrieval.IndexStateError, "stale"),
        ):
            self.retrieval.command_semantic(self.root, args)

    def test_artifact_reads_and_dependency_loader_failures_are_lane_unavailable(
        self,
    ) -> None:
        model = self.root / "model.onnx"
        tokenizer = self.root / "tokenizer.json"
        model.write_bytes(b"model")
        tokenizer.write_text("{}", encoding="utf-8")
        provider = self.retrieval.OnnxSemanticProvider(model, tokenizer)

        with mock.patch.object(Path, "read_bytes", side_effect=OSError("read denied")):
            with self.assertRaises(self.retrieval.SemanticLaneUnavailable):
                _ = provider.model_identity

        with mock.patch("builtins.__import__", side_effect=OSError("loader failed")):
            with self.assertRaises(self.retrieval.SemanticLaneUnavailable):
                provider.embed(["query"])

    def test_onnx_provider_bounds_tokenizer_width_and_batch_size(self) -> None:
        provider = self.retrieval.OnnxSemanticProvider(
            self.root / "unused.onnx",
            self.root / "unused-tokenizer.json",
            max_sequence_length=5,
            batch_size=2,
        )
        tokenizer = RecordingTokenizer(maximum=1000)
        session = RecordingSession()
        provider._tokenizer = tokenizer
        provider._session = session
        provider._numpy = FakeNumpy

        vectors = provider.embed(["a" * 100] * 5)

        self.assertEqual(len(vectors), 5)
        self.assertEqual(tokenizer.batch_sizes, [2, 2, 1])
        self.assertEqual(session.input_shapes, [(2, 5), (2, 5), (1, 5)])

    def test_preprocessing_identity_covers_sequence_output_and_pooling(self) -> None:
        base = self.retrieval.OnnxSemanticProvider(
            Path("model"), Path("tokenizer"), max_sequence_length=32
        )
        variants = (
            self.retrieval.OnnxSemanticProvider(
                Path("model"), Path("tokenizer"), max_sequence_length=64
            ),
            self.retrieval.OnnxSemanticProvider(
                Path("model"), Path("tokenizer"), output_index=1
            ),
            self.retrieval.OnnxSemanticProvider(
                Path("model"), Path("tokenizer"), pooling="cls"
            ),
        )
        self.assertEqual(
            len(
                {
                    base.preprocessing_identity,
                    *(item.preprocessing_identity for item in variants),
                }
            ),
            4,
        )

    def test_all_semantic_pipeline_exceptions_are_lane_unavailable(self) -> None:
        class RaisingTokenizer:
            def encode_batch(self, _texts):
                raise RuntimeError("tokenizer boom")

        class BrokenEncodingTokenizer:
            def encode_batch(self, _texts):
                return [object()]

        class RaisingInputsSession:
            def get_inputs(self):
                raise RuntimeError("inputs boom")

        class RaisingRunSession(RecordingSession):
            def run(self, _outputs, _feed):
                raise RuntimeError("inference boom")

        cases = (
            (RaisingTokenizer(), RecordingSession(), 0),
            (BrokenEncodingTokenizer(), RecordingSession(), 0),
            (RecordingTokenizer(5), RaisingInputsSession(), 0),
            (RecordingTokenizer(5), RaisingRunSession(), 0),
            (RecordingTokenizer(5), RecordingSession(), 1),
        )
        for tokenizer, session, output_index in cases:
            with self.subTest(session=type(session).__name__, output=output_index):
                provider = self.retrieval.OnnxSemanticProvider(
                    Path("model"), Path("tokenizer"), output_index=output_index
                )
                provider._tokenizer = tokenizer
                provider._session = session
                provider._numpy = FakeNumpy
                with self.assertRaises(self.retrieval.SemanticLaneUnavailable):
                    provider.embed(["query"])

    def test_status_never_reports_incomplete_or_corrupt_cohort_ready(self) -> None:
        with self.persist_fake_embeddings() as connection:
            connection.execute("DELETE FROM chunk_embeddings WHERE rowid = 1")
            connection.commit()
        partial = json.loads(self.run_cli("status").stdout)
        self.assertEqual(partial["state"], "ready")
        self.assertEqual(partial["semantic_lane"], "unavailable")
        self.assertIn("vector_rows", partial["semantic_reasons"])

        self.run_cli("rebuild")
        with self.persist_fake_embeddings() as connection:
            connection.execute(
                "UPDATE chunk_embeddings SET vector_fingerprint = 'corrupt'"
            )
            connection.commit()
        corrupt = json.loads(self.run_cli("status").stdout)
        self.assertEqual(corrupt["semantic_lane"], "unavailable")
        self.assertIn("vector_fingerprints", corrupt["semantic_reasons"])

    def test_doctor_rejects_corrupt_vector_fingerprints(self) -> None:
        with self.persist_fake_embeddings() as connection:
            connection.execute(
                "UPDATE chunk_embeddings SET vector_fingerprint = 'corrupt'"
            )
            connection.commit()
        result = self.run_cli("doctor", expected_returncode=1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["state"], "stale")
        self.assertIn("vector_fingerprints", payload["stale_reasons"])
        self.assertEqual(payload["semantic_lane"], "unavailable")

    def test_doctor_rejects_stale_and_partial_embedding_cohorts(self) -> None:
        with self.persist_fake_embeddings() as connection:
            connection.execute(
                "UPDATE chunk_embeddings SET chunk_hash = 'stale' WHERE rowid = 1"
            )
            connection.commit()
        stale = self.run_cli("doctor", expected_returncode=1)
        self.assertIn("vector_rows", json.loads(stale.stdout)["stale_reasons"])

        self.run_cli("rebuild")
        with self.persist_fake_embeddings() as connection:
            connection.execute("DELETE FROM chunk_embeddings WHERE rowid = 1")
            connection.commit()
        partial = self.run_cli("doctor", expected_returncode=1)
        self.assertIn("vector_rows", json.loads(partial.stdout)["stale_reasons"])

    def test_lanes_keep_separate_ranks_and_deduplicate_lexical_first(self) -> None:
        concepts = self.root / "wiki" / "concepts"
        (concepts / "alpha.md").write_text(
            "# Alpha\nVector one links to [[shared]].\n", encoding="utf-8"
        )
        (concepts / "shared.md").write_text(
            "# Shared\nLinked context.\n", encoding="utf-8"
        )
        self.run_cli("rebuild")
        connection = sqlite3.connect(self.root / "state" / "wiki_index.sqlite")
        connection.row_factory = sqlite3.Row
        self.addCleanup(connection.close)
        result = self.retrieval.persist_embeddings(
            connection, FakeEmbedder(), "fake-model-v1", "fake-tokenizer-v1"
        )
        self.assertEqual(result["embedded_chunks"], 3)
        with connection:
            lexical = self.retrieval.lexical_rows(connection, "Alpha", 10)
            semantic = self.retrieval.semantic_rows(
                connection, [1.0, 0.0], "fake-model-v1", "fake-tokenizer-v1", 2
            )
            lexical, semantic = self.retrieval.prepare_lane_rows(lexical, semantic)
            self.retrieval.attach_lane_neighbors(
                connection, (lexical, semantic), 1, 5, 50
            )

        self.assertEqual([row["title"] for row in lexical], ["Alpha"])
        self.assertEqual([row["title"] for row in semantic], ["Beta"])
        self.assertEqual(lexical[0]["lane_rank"], 1)
        self.assertEqual(semantic[0]["lane_rank"], 1)
        self.assertEqual(semantic[0]["candidate_role"], "similarity_candidate")
        self.assertEqual(semantic[0]["provenance"]["truth_source"], "markdown")
        self.assertNotEqual(lexical[0]["chunk_id"], semantic[0]["chunk_id"])
        self.assertEqual([row["title"] for row in lexical[0]["neighbors"]], ["Shared"])
        self.assertEqual(
            lexical[0]["neighbors"][0]["provenance"]["relation"], "resolved_wikilink"
        )

    def test_search_freshness_uses_weakest_requested_lane_guarantee(self) -> None:
        semantic_row = {
            "chunk_id": "semantic-candidate",
            "page_id": "semantic-page",
            "path": "wiki/concepts/semantic.md",
            "title": "Semantic",
            "chunk_index": 0,
            "heading_path": "Semantic",
            "line_start": 1,
            "line_end": 2,
            "byte_start": 0,
            "byte_end": 1,
            "semantic_score": 1.0,
        }

        def query(mode: str) -> dict[str, object]:
            output = io.StringIO()
            args = argparse.Namespace(
                query="Alpha",
                mode=mode,
                limit=10,
                neighbor_limit=5,
                graph_cap=50,
                hops=0,
            )
            with (
                mock.patch.object(
                    self.retrieval, "semantic_candidates", return_value=[semantic_row]
                ),
                mock.patch("sys.stdout", output),
            ):
                self.assertEqual(self.retrieval.command_search(self.root, args), 0)
            return json.loads(output.getvalue())

        lexical = query("lexical")
        semantic = query("semantic")
        both = query("both")

        self.assertEqual(lexical["freshness"], "unchecked")
        self.assertEqual(lexical["lanes"]["lexical"]["freshness"], "unchecked")
        self.assertEqual(semantic["freshness"], "stat")
        self.assertEqual(semantic["lanes"]["semantic"]["freshness"], "stat")
        self.assertEqual(both["freshness"], "unchecked")
        self.assertEqual(both["lanes"]["lexical"]["freshness"], "unchecked")
        self.assertEqual(both["lanes"]["semantic"]["freshness"], "stat")

    def test_refresh_reuses_vectors_and_embeds_only_changed_chunks(self) -> None:
        provider = RefreshFakeProvider()
        args = argparse.Namespace(
            chunk_threshold=self.retrieval.indexer.DEFAULT_CHUNK_THRESHOLD,
            model_path="configured-model.onnx",
            tokenizer_path="configured-tokenizer.json",
            max_sequence_length=self.retrieval.DEFAULT_MAX_SEQUENCE_LENGTH,
            batch_size=self.retrieval.DEFAULT_EMBED_BATCH_SIZE,
            output_index=self.retrieval.DEFAULT_OUTPUT_INDEX,
            pooling=self.retrieval.DEFAULT_POOLING,
        )

        first = self.retrieval.refresh_retrieval(
            self.root, args, provider_factory=lambda _args: provider
        )
        self.assertTrue(first["retrieval_ready"])
        self.assertEqual(first["semantic_status"], "ready")
        self.assertEqual(first["embedded_chunks"], 2)
        self.assertIsNotNone(first["corpus_fingerprint"])
        self.assertIsNotNone(first["semantic_cohort_fingerprint"])
        first_cohort_fingerprint = first["semantic_cohort_fingerprint"]

        provider.calls.clear()
        second = self.retrieval.refresh_retrieval(
            self.root, args, provider_factory=lambda _args: provider
        )
        self.assertEqual(second["embedded_chunks"], 0)
        self.assertEqual(second["reused_chunks"], 2)
        self.assertEqual(provider.calls, [])

        alpha = self.root / "wiki" / "concepts" / "alpha.md"
        alpha.write_text("# Alpha\nVector one changed.\n", encoding="utf-8")
        third = self.retrieval.refresh_retrieval(
            self.root, args, provider_factory=lambda _args: provider
        )
        self.assertEqual(third["embedded_chunks"], 1)
        self.assertEqual(third["reused_chunks"], 1)
        self.assertEqual(len(provider.calls), 1)
        self.assertNotEqual(
            third["semantic_cohort_fingerprint"], first_cohort_fingerprint
        )

    def test_refresh_without_onnx_configuration_keeps_lexical_ready(self) -> None:
        args = argparse.Namespace(
            chunk_threshold=self.retrieval.indexer.DEFAULT_CHUNK_THRESHOLD,
            model_path=None,
            tokenizer_path=None,
            max_sequence_length=self.retrieval.DEFAULT_MAX_SEQUENCE_LENGTH,
            batch_size=self.retrieval.DEFAULT_EMBED_BATCH_SIZE,
            output_index=self.retrieval.DEFAULT_OUTPUT_INDEX,
            pooling=self.retrieval.DEFAULT_POOLING,
        )
        with mock.patch.dict(
            self.retrieval.os.environ,
            {"WIKI_ONNX_MODEL": "", "WIKI_TOKENIZER": ""},
        ):
            result = self.retrieval.refresh_retrieval(self.root, args)
        self.assertTrue(result["retrieval_ready"])
        self.assertEqual(result["lexical_status"], "ready")
        self.assertEqual(result["semantic_status"], "unavailable")

    def test_refresh_with_missing_onnx_artifacts_is_non_blocking(self) -> None:
        args = argparse.Namespace(
            chunk_threshold=self.retrieval.indexer.DEFAULT_CHUNK_THRESHOLD,
            model_path=str(self.root / "missing-model.onnx"),
            tokenizer_path=str(self.root / "missing-tokenizer.json"),
            max_sequence_length=self.retrieval.DEFAULT_MAX_SEQUENCE_LENGTH,
            batch_size=self.retrieval.DEFAULT_EMBED_BATCH_SIZE,
            output_index=self.retrieval.DEFAULT_OUTPUT_INDEX,
            pooling=self.retrieval.DEFAULT_POOLING,
        )
        result = self.retrieval.refresh_retrieval(self.root, args)
        self.assertTrue(result["retrieval_ready"])
        self.assertEqual(result["lexical_status"], "ready")
        self.assertEqual(result["semantic_status"], "unavailable")
        self.assertIn("missing", result["semantic_reason"])


if __name__ == "__main__":
    unittest.main()
