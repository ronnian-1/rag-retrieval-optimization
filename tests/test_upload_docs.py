"""Run with: python -B -m unittest discover -s tests -p test_upload_docs.py -v.

The real route and loader modules run against temporary files. Import stubs
replace configuration, database, model, parser and splitter dependencies:
no settings/.env import, API call, or existing knowledge base access.
"""
import asyncio
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException, UploadFile


ROOT = Path(__file__).resolve().parents[1]


class Document:
    def __init__(self, page_content, metadata=None):
        self.page_content = page_content
        self.metadata = metadata or {}


class Loader:
    def __init__(self, path, **kwargs):
        self.path = path
        self.kwargs = kwargs

    def load(self):
        text = Path(self.path).read_text(encoding="utf-8")
        return [Document(text, {"source": self.path, "page": 2, "row": 3})]


class Splitter:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def split_documents(self, docs):
        return [
            Document(doc.page_content.strip(), copy.deepcopy(doc.metadata))
            for doc in docs if doc.page_content.strip()
        ]


def stub_module(name, **attributes):
    module = ModuleType(name)
    module.__dict__.update(attributes)
    return module


def load_routes(temp_root):
    """Import production modules with all sensitive/external imports replaced."""
    identity = lambda *args, **kwargs: lambda function: function
    router = SimpleNamespace(post=identity, get=identity, delete=identity)
    modules = {
        "fastapi": stub_module(
            "fastapi", HTTPException=HTTPException, UploadFile=UploadFile,
            APIRouter=lambda **kwargs: router,
            Body=lambda *args, **kwargs: None, Depends=lambda *args: None,
            File=lambda *args, **kwargs: None, Form=lambda *args, **kwargs: None,
        ),
        "configs": stub_module("configs", __path__=[]),
        "configs.settings": stub_module(
            "configs.settings", KB_DIR=str(temp_root / "knowledgebases"),
            FILE_STORAGE_DIR=str(temp_root / "data"),
            embedding_model_path=None, api_key=None, base_url=None,
            embedding_model_name=None,
        ),
        "db_server": stub_module("db_server", __path__=[]),
        "db_server.base": stub_module("db_server.base", get_db=Mock()),
        "db_server.knowledge_base_repository": stub_module(
            "db_server.knowledge_base_repository",
            add_kb_to_db=Mock(), del_kb_from_db=Mock(), list_kb_from_db=Mock(),
        ),
        "sqlalchemy": stub_module("sqlalchemy", __path__=[]),
        "sqlalchemy.orm": stub_module("sqlalchemy.orm", Session=object),
        "jieba": stub_module("jieba"),
        "langchain_openai": stub_module("langchain_openai", OpenAIEmbeddings=Mock()),
        "langchain": stub_module("langchain", __path__=[]),
        "langchain.embeddings": stub_module("langchain.embeddings", __path__=[]),
        "langchain.embeddings.base": stub_module("langchain.embeddings.base", Embeddings=object),
        "langchain.retrievers": stub_module("langchain.retrievers", EnsembleRetriever=Mock()),
        "langchain.text_splitter": stub_module(
            "langchain.text_splitter", RecursiveCharacterTextSplitter=Splitter,
        ),
        "langchain_core": stub_module("langchain_core", __path__=[]),
        "langchain_core.documents": stub_module("langchain_core.documents", Document=Document),
        "langchain_community": stub_module("langchain_community", __path__=[]),
        "langchain_community.retrievers": stub_module("langchain_community.retrievers", BM25Retriever=Mock()),
        "langchain_community.vectorstores": stub_module("langchain_community.vectorstores", FAISS=Mock()),
        "langchain_community.embeddings": stub_module("langchain_community.embeddings", HuggingFaceBgeEmbeddings=Mock()),
        "langchain_community.document_loaders": stub_module(
            "langchain_community.document_loaders",
            TextLoader=Loader, CSVLoader=Loader, PyPDFLoader=Loader,
            UnstructuredMarkdownLoader=Loader,
        ),
        "knowledgebase_server": stub_module(
            "knowledgebase_server", __path__=[str(ROOT / "knowledgebase_server")],
        ),
        "knowledgebase_server.loader": stub_module(
            "knowledgebase_server.loader",
            __path__=[str(ROOT / "knowledgebase_server" / "loader")],
        ),
    }
    loader_name = "knowledgebase_server.loader.loader"
    route_name = "knowledgebase_server.kb_routes"
    for name, path in (
        (loader_name, ROOT / "knowledgebase_server" / "loader" / "loader.py"),
        (route_name, ROOT / "knowledgebase_server" / "kb_routes.py"),
    ):
        spec = importlib.util.spec_from_file_location(name, path)
        modules[name] = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, modules):
        modules[loader_name].__spec__.loader.exec_module(modules[loader_name])
        modules[route_name].__spec__.loader.exec_module(modules[route_name])
    return modules[route_name]


class VectorStore:
    def __init__(self, path):
        rows = json.loads((Path(path) / "index.pkl").read_text(encoding="utf-8"))
        self.docstore = SimpleNamespace(_dict={
            str(i): Document(row["text"], row["metadata"])
            for i, row in enumerate(rows)
        })
        self.add_documents = Mock(side_effect=self.add)
        self.save_local = Mock(side_effect=self.save)

    def add(self, docs):
        for doc in docs:
            self.docstore._dict[str(len(self.docstore._dict))] = copy.deepcopy(doc)

    def save(self, path):
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        (path / "index.faiss").write_bytes(b"mock vectors")
        rows = [
            {"text": doc.page_content, "metadata": doc.metadata}
            for doc in self.docstore._dict.values()
        ]
        (path / "index.pkl").write_text(json.dumps(rows), encoding="utf-8")


class UploadDocsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rag-upload-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.kb = self.root / "knowledgebases" / "test.faiss"
        self.storage = self.root / "data" / "test"
        self.kb.mkdir(parents=True)
        self.storage.mkdir(parents=True)
        (self.storage / "old.txt").write_bytes(b"original")
        (self.kb / "index.faiss").write_bytes(b"original vectors")
        (self.kb / "index.pkl").write_text(json.dumps([{
            "text": "original",
            "metadata": {"filename": "old.txt", "chunk_id": 0, "source": str(self.storage / "old.txt")},
        }]), encoding="utf-8")
        self.routes = load_routes(self.root)
        self.stores = []
        self.routes.get_embedding_model = Mock(return_value=object())
        self.routes.FAISS = SimpleNamespace(load_local=Mock(side_effect=self.load_store))
        self.before = self.snapshot()

    def load_store(self, path, *args, **kwargs):
        store = VectorStore(path)
        self.stores.append(store)
        return store

    def snapshot(self):
        return {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in self.root.rglob("*") if path.is_file()
        }

    def upload(self, pairs, size=128, overlap=20, kb_name="test"):
        files = [UploadFile(filename=name, file=io.BytesIO(data)) for name, data in pairs]
        return asyncio.run(self.routes.upload_docs(
            files=files, kb_name=kb_name, chunk_size=size, chunk_overlap=overlap,
        ))

    def assert_failure(self, code, pairs, **kwargs):
        with self.assertRaises(HTTPException) as caught:
            self.upload(pairs, **kwargs)
        self.assertEqual(code, caught.exception.status_code)
        self.assertEqual(self.before, self.snapshot())
        return caught.exception

    def test_invalid_parameters_are_rejected_before_reading_files(self):
        for size, overlap in ((0, 0), (-1, 0), (10, -1), (10, 10), (10, 11)):
            with self.subTest(size=size, overlap=overlap):
                self.assert_failure(400, [("new.txt", b"new")], size=size, overlap=overlap)
        self.routes.FAISS.load_local.assert_not_called()

    def test_no_files(self):
        self.assert_failure(400, [])

    def test_missing_knowledge_base(self):
        self.assert_failure(404, [("new.txt", b"new")], kb_name="missing")

    def test_later_unsupported_file_rejects_whole_batch(self):
        self.assert_failure(400, [("new.txt", b"new"), ("bad.exe", b"bad")])
        self.routes.get_embedding_model.assert_not_called()

    def test_invalid_filename(self):
        self.assert_failure(400, [("..", b"new")])

    def test_success_keeps_old_docs_and_preserves_metadata(self):
        result = self.upload([("one.TXT", b"one"), ("two.csv", b"two")], size=50, overlap=5)
        self.assertIn("message", result)
        self.assertEqual(["one.TXT", "two.csv"], result["added_files"])
        self.assertEqual([], result["skipped_files"])
        self.assertEqual("committed", result["transaction_state"])
        store = self.stores[-1]
        store.add_documents.assert_called_once()
        store.save_local.assert_called_once()
        self.assertNotEqual(str(self.kb), store.save_local.call_args.args[0])
        self.assertEqual(3, len(VectorStore(self.kb).docstore._dict))
        for doc in list(store.docstore._dict.values())[1:]:
            self.assertEqual(str(self.storage / doc.metadata["filename"]), doc.metadata["source"])
            self.assertEqual(0, doc.metadata["chunk_id"])
            self.assertEqual("test", doc.metadata["kb_name"])
            self.assertEqual(2, doc.metadata["page"])
            self.assertEqual(3, doc.metadata["row"])
        self.assertFalse(Path(str(self.kb) + ".upload.lock").exists())
        self.assertFalse(list(self.kb.parent.glob(".upload-*")))

    def test_identical_existing_file_skips_without_resaving(self):
        result = self.upload([("old.txt", b"original")], size=50, overlap=0)
        self.assertEqual([], result["added_files"])
        self.assertEqual(["old.txt"], result["skipped_files"])
        self.stores[-1].add_documents.assert_not_called()
        self.stores[-1].save_local.assert_not_called()
        self.assertEqual(self.before, self.snapshot())

    def test_retry_after_success_does_not_accumulate_chunks(self):
        self.upload([("new.txt", b"new")])
        committed = self.snapshot()
        result = self.upload([("new.txt", b"new")])
        self.assertEqual(["new.txt"], result["skipped_files"])
        self.assertEqual(committed, self.snapshot())
        self.assertEqual(2, len(self.stores[-1].docstore._dict))
        self.stores[-1].add_documents.assert_not_called()

    def test_mixed_skipped_and_new_files(self):
        result = self.upload([("old.txt", b"original"), ("new.txt", b"new")])
        self.assertEqual(["new.txt"], result["added_files"])
        self.assertEqual(["old.txt"], result["skipped_files"])
        self.assertEqual(2, len(VectorStore(self.kb).docstore._dict))

    def test_same_name_different_content_rejects_entire_batch(self):
        self.assert_failure(409, [("new.txt", b"new"), ("old.txt", b"changed")])
        self.routes.get_embedding_model.assert_not_called()

    def test_duplicate_names_in_batch_identical_are_added_once(self):
        result = self.upload([("new.txt", b"new"), ("new.txt", b"new")])
        self.assertEqual(["new.txt"], result["added_files"])
        self.assertEqual(["new.txt"], result["skipped_files"])
        self.assertEqual(2, len(VectorStore(self.kb).docstore._dict))

    def test_duplicate_names_in_batch_conflict_rejects_everything(self):
        self.assert_failure(409, [("new.txt", b"one"), ("new.txt", b"two")])

    def test_parser_failure_in_later_file_never_adds_first_file(self):
        self.assert_failure(400, [("new.txt", b"new"), ("bad.txt", b"\xff")])
        self.stores[-1].add_documents.assert_not_called()

    def test_empty_and_whitespace_documents(self):
        for content in (b"", b" \t\n "):
            with self.subTest(content=content):
                self.assert_failure(400, [("blank.txt", content)])
                self.stores[-1].add_documents.assert_not_called()

    def test_splitter_failure(self):
        with patch.object(Splitter, "split_documents", side_effect=ValueError("split failed")):
            self.assert_failure(400, [("new.txt", b"new")])
        self.stores[-1].add_documents.assert_not_called()

    def test_embedding_failure_does_not_change_disk(self):
        real_add = VectorStore.add
        def fail_after_adding(store, docs):
            real_add(store, docs)
            raise RuntimeError("mock embedding failure")
        with patch.object(VectorStore, "add", fail_after_adding):
            self.assert_failure(500, [("new.txt", b"new")])

    def test_staged_save_failure_does_not_change_disk(self):
        def fail_save(store, path):
            Path(path).mkdir()
            (Path(path) / "index.faiss").write_bytes(b"partial")
            raise OSError("mock disk failure")
        with patch.object(VectorStore, "save", fail_save):
            self.assert_failure(500, [("new.txt", b"new")])

    def test_backup_failure_does_not_change_disk(self):
        with patch.object(self.routes.shutil, "copy2", side_effect=OSError("mock backup failure")):
            self.assert_failure(500, [("new.txt", b"new")])

    def test_partial_original_write_rolls_back_all_new_originals(self):
        real_copy = self.routes.shutil.copyfileobj
        calls = []
        def fail_second(source, target, *args):
            calls.append(target.name)
            if len(calls) == 2:
                target.write(b"partial")
                raise OSError("mock original write failure")
            return real_copy(source, target, *args)
        with patch.object(self.routes.shutil, "copyfileobj", side_effect=fail_second):
            self.assert_failure(500, [("one.txt", b"one"), ("two.txt", b"two")])

    def test_first_index_replace_failure_rolls_back_originals(self):
        with patch.object(self.routes.os, "replace", side_effect=OSError("mock replace failure")):
            self.assert_failure(500, [("new.txt", b"new")])

    def test_second_index_replace_failure_restores_first_index(self):
        real_replace = os.replace
        def fail_second(source, target):
            if Path(source).parent.name == "index" and Path(source).name == "index.pkl":
                raise OSError("mock second replacement failure")
            return real_replace(source, target)
        with patch.object(self.routes.os, "replace", side_effect=fail_second):
            self.assert_failure(500, [("new.txt", b"new")])

    def test_interrupt_between_index_updates_restores_exact_disk_state(self):
        real_replace = os.replace
        interruption = KeyboardInterrupt("between index updates")
        def interrupt_second(source, target):
            if Path(source).parent.name == "index" and Path(source).name == "index.pkl":
                self.assertEqual(b"new", (self.storage / "new.txt").read_bytes())
                self.assertEqual(b"mock vectors", (self.kb / "index.faiss").read_bytes())
                self.assertEqual(self.before["knowledgebases/test.faiss/index.pkl"], (self.kb / "index.pkl").read_bytes())
                raise interruption
            return real_replace(source, target)
        with patch.object(self.routes.os, "replace", side_effect=interrupt_second):
            with self.assertRaises(KeyboardInterrupt) as caught:
                self.upload([("new.txt", b"new")])
        self.assertIs(interruption, caught.exception)
        self.assertEqual(self.before, self.snapshot())
        self.assertFalse(list(self.kb.parent.glob(".upload-*")))
        self.assertEqual(1, len(VectorStore(self.kb).docstore._dict))

    def test_interrupt_after_index_replace_before_bookkeeping_rolls_back(self):
        real_replace = os.replace
        def interrupt_after_replace(source, target):
            real_replace(source, target)
            if Path(source).parent.name == "index":
                raise KeyboardInterrupt("replacement completed")
        with patch.object(self.routes.os, "replace", side_effect=interrupt_after_replace):
            with self.assertRaises(KeyboardInterrupt):
                self.upload([("new.txt", b"new")])
        self.assertEqual(self.before, self.snapshot())
        self.assertFalse(list(self.kb.parent.glob(".upload-*")))

    def test_interrupted_original_creation_with_uncertain_ownership_blocks_uploads(self):
        real_open = open
        new_file = self.storage / "new.txt"
        def interrupt_creation(path, mode="r", *args, **kwargs):
            if Path(path) == new_file and mode == "xb":
                with real_open(path, mode):
                    pass
                raise KeyboardInterrupt("created before ownership recorded")
            return real_open(path, mode, *args, **kwargs)
        with patch("builtins.open", side_effect=interrupt_creation):
            with self.assertLogs(self.routes.logger, level="ERROR"):
                with self.assertRaises(KeyboardInterrupt):
                    self.upload([("new.txt", b"new")])
        self.assertEqual(b"", new_file.read_bytes())
        self.assertTrue(Path(str(self.kb) + ".upload.lock").exists())
        recovery, = self.kb.parent.glob(".upload-*")
        for name in ("index.faiss", "index.pkl"):
            self.assertEqual(self.before[f"knowledgebases/test.faiss/{name}"], (self.kb / name).read_bytes())
            self.assertEqual((self.kb / name).read_bytes(), (recovery / name).read_bytes())
        self.assertEqual(b"new", (recovery / "0.txt").read_bytes())
        blocked = self.snapshot()
        with self.assertRaises(HTTPException) as busy:
            self.upload([("another.txt", b"another")])
        self.assertEqual(409, busy.exception.status_code)
        self.assertEqual(blocked, self.snapshot())

    def test_successful_commit_survives_lock_release_failure(self):
        real_remove = os.remove
        lock = Path(str(self.kb) + ".upload.lock")
        def fail_lock_remove(path, *args, **kwargs):
            if Path(path) == lock:
                raise PermissionError("lock deletion denied")
            return real_remove(path, *args, **kwargs)
        with patch.object(self.routes.os, "remove", side_effect=fail_lock_remove):
            with self.assertLogs(self.routes.logger, level="ERROR") as logs:
                result = self.upload([("new.txt", b"new")])
        self.assertEqual("committed", result["transaction_state"])
        self.assertEqual(["new.txt"], result["added_files"])
        self.assertTrue(any("lock release failed; state=committed" in line for line in logs.output))
        self.assertEqual(b"new", (self.storage / "new.txt").read_bytes())
        self.assertEqual(b"original", (self.storage / "old.txt").read_bytes())
        self.assertEqual(b"mock vectors", (self.kb / "index.faiss").read_bytes())
        self.assertEqual(["original", "new"], [doc.page_content for doc in VectorStore(self.kb).docstore._dict.values()])
        self.assertTrue(lock.exists())
        self.assertFalse(list(self.kb.parent.glob(".upload-*")))
        committed = self.snapshot()
        with self.assertRaises(HTTPException) as busy:
            self.upload([("another.txt", b"another")])
        self.assertEqual(409, busy.exception.status_code)
        self.assertEqual(committed, self.snapshot())

    def test_conflict_survives_lock_release_failure(self):
        lock = Path(str(self.kb) + ".upload.lock")
        with patch.object(self.routes.os, "remove", side_effect=PermissionError("lock deletion denied")):
            with self.assertLogs(self.routes.logger, level="ERROR") as logs:
                with self.assertRaises(HTTPException) as caught:
                    self.upload([("new.txt", b"new"), ("old.txt", b"changed")])
        self.assertEqual(409, caught.exception.status_code)
        self.assertIn("different content", caught.exception.detail)
        self.assertTrue(any("lock release failed; state=preparing" in line for line in logs.output))
        self.assertTrue(lock.exists())
        expected = {**self.before, lock.relative_to(self.root).as_posix(): b""}
        self.assertEqual(expected, self.snapshot())
        self.assertFalse(list(self.kb.parent.glob(".upload-*")))

    def test_staging_cleanup_failure_preserves_committed_result(self):
        with patch.object(self.routes.shutil, "rmtree", side_effect=PermissionError("cleanup denied")):
            with self.assertLogs(self.routes.logger, level="ERROR") as logs:
                result = self.upload([("new.txt", b"new")])
        self.assertEqual("committed", result["transaction_state"])
        self.assertTrue(any("recovery cleanup failed; state=committed" in line for line in logs.output))
        self.assertEqual(b"new", (self.storage / "new.txt").read_bytes())
        self.assertEqual(2, len(VectorStore(self.kb).docstore._dict))
        self.assertEqual(1, len(list(self.kb.parent.glob(".upload-*"))))
        self.assertFalse(Path(str(self.kb) + ".upload.lock").exists())

    def test_interrupt_with_failed_rollback_keeps_recovery_and_lock(self):
        self.check_interrupted_rollback(KeyboardInterrupt("commit interrupted"), OSError("restore failed"))

    def test_interrupt_during_rollback_keeps_recovery_and_lock(self):
        self.check_interrupted_rollback(OSError("commit failed"), KeyboardInterrupt("rollback interrupted"))

    def check_interrupted_rollback(self, commit_error, rollback_error):
        real_replace = os.replace
        def fail_commit_and_restore(source, target):
            source = Path(source)
            if source.parent.name == "index" and source.name == "index.pkl":
                raise commit_error
            if source.parent.name.startswith(".upload-"):
                raise rollback_error
            return real_replace(source, target)
        with patch.object(self.routes.os, "replace", side_effect=fail_commit_and_restore):
            with self.assertLogs(self.routes.logger, level="ERROR") as logs:
                with self.assertRaises(KeyboardInterrupt) as caught:
                    self.upload([("new.txt", b"new")])
        self.assertIs(commit_error if isinstance(commit_error, KeyboardInterrupt) else rollback_error, caught.exception)
        self.assertTrue(any("rollback incomplete" in line for line in logs.output))
        self.assertTrue(Path(str(self.kb) + ".upload.lock").exists())
        recovery, = self.kb.parent.glob(".upload-*")
        for name in ("index.faiss", "index.pkl"):
            self.assertEqual(self.before[f"knowledgebases/test.faiss/{name}"], (recovery / name).read_bytes())
        self.assertEqual(b"new", (recovery / "0.txt").read_bytes())
        self.assertEqual(b"mock vectors", (self.kb / "index.faiss").read_bytes())
        self.assertEqual(self.before["knowledgebases/test.faiss/index.pkl"], (self.kb / "index.pkl").read_bytes())
        self.assertFalse((self.storage / "new.txt").exists())
        blocked = self.snapshot()
        with self.assertRaises(HTTPException) as busy:
            self.upload([("another.txt", b"another")])
        self.assertEqual(409, busy.exception.status_code)
        self.assertEqual(blocked, self.snapshot())

    def test_incomplete_rollback_retains_backups_and_blocks_uploads(self):
        real_replace = os.replace
        def fail_commit_and_restore(source, target):
            source = Path(source)
            if source.name == "index.pkl" or source.parent.name.startswith(".upload-"):
                raise OSError("mock rollback failure")
            return real_replace(source, target)
        with patch.object(self.routes.os, "replace", side_effect=fail_commit_and_restore):
            with self.assertRaises(HTTPException) as caught:
                self.upload([("new.txt", b"new")])
        self.assertEqual(500, caught.exception.status_code)
        self.assertIn("rollback incomplete", caught.exception.detail)
        self.assertTrue(Path(str(self.kb) + ".upload.lock").exists())
        recovery = list(self.kb.parent.glob(".upload-*"))
        self.assertEqual(1, len(recovery))
        self.assertEqual(self.before["knowledgebases/test.faiss/index.faiss"], (recovery[0] / "index.faiss").read_bytes())
        with self.assertRaises(HTTPException) as busy:
            self.upload([("another.txt", b"another")])
        self.assertEqual(409, busy.exception.status_code)

    def test_existing_upload_lock_is_not_removed(self):
        lock = Path(str(self.kb) + ".upload.lock")
        lock.write_text("another upload", encoding="utf-8")
        self.before = self.snapshot()
        self.assert_failure(409, [("new.txt", b"new")])
        self.assertTrue(lock.exists())

    def test_existing_unindexed_original_can_be_ingested_without_overwriting(self):
        orphan = self.storage / "orphan.txt"
        orphan.write_bytes(b"orphan")
        timestamp = orphan.stat().st_mtime_ns
        result = self.upload([("orphan.txt", b"orphan")])
        self.assertEqual(["orphan.txt"], result["added_files"])
        self.assertEqual(timestamp, orphan.stat().st_mtime_ns)
        self.assertEqual(2, len(VectorStore(self.kb).docstore._dict))

    def test_indexed_filename_without_original_is_rejected(self):
        (self.storage / "old.txt").unlink()
        self.before = self.snapshot()
        self.assert_failure(409, [("old.txt", b"original")])

    def test_exclusive_creation_does_not_overwrite_an_outside_writer(self):
        real_open = open
        def collide(path, mode="r", *args, **kwargs):
            if str(path) == str(self.storage / "new.txt") and mode == "xb":
                with real_open(path, "wb") as target:
                    target.write(b"outside writer")
            return real_open(path, mode, *args, **kwargs)
        with patch("builtins.open", side_effect=collide):
            with self.assertRaises(HTTPException) as caught:
                self.upload([("new.txt", b"new")])
        self.assertEqual(500, caught.exception.status_code)
        self.assertEqual(b"outside writer", (self.storage / "new.txt").read_bytes())
        self.assertEqual(self.before["knowledgebases/test.faiss/index.pkl"], (self.kb / "index.pkl").read_bytes())

    def test_loader_accepts_uppercase_supported_extensions(self):
        for extension in (".TXT", ".PDF", ".CSV", ".MD"):
            with self.subTest(extension=extension):
                loader = self.routes.data_loader().get_loader("example" + extension)
                self.assertIsInstance(loader, Loader)
        self.assertEqual({"encoding": "utf-8"}, self.routes.data_loader().get_loader("example.TXT").kwargs)


if __name__ == "__main__":
    unittest.main()
