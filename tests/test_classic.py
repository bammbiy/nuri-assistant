from __future__ import annotations

import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from src.nuri_assistant import (
    DEFAULT_RULE,
    HistoryStore,
    ProductCandidate,
    ShoppingAdvisorError,
    RenameError,
    RenameInput,
    WorkProfile,
    apply_batch_rename,
    advise_purchase,
    build_file_name,
    export_preview_csv,
    infer_metadata,
    interpret_file_command,
    load_profiles,
    preview_batch,
    preview_rename,
    evaluate_purchase,
    scan_files,
    save_profile,
    undo_last_batch,
)
from src.nuri_assistant.classic.core import rule_from_korean, rule_pattern, rule_to_korean, validate_rule
from src.nuri_assistant.classic.tools import FileTools, RenameAction, RenameOptions, resolve_folder


class RenameEngineTest(unittest.TestCase):
    def test_build_file_name_with_default_rule(self) -> None:
        item = RenameInput(Path("sample.PDF"), "2026-06-28", "JA00", "7", DEFAULT_RULE)

        self.assertEqual(build_file_name(item), "20260628_ja00_007.pdf")

    def test_infer_metadata_from_existing_name(self) -> None:
        metadata = infer_metadata(Path("20260628_ja00_p12.pdf"))

        self.assertEqual(metadata["date"], "20260628")
        self.assertEqual(metadata["media"], "ja00")
        self.assertEqual(metadata["page"], "012")

    def test_preview_detects_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.pdf"
            target = root / "20260628_ja00_001.pdf"
            source.write_text("source", encoding="utf-8")
            target.write_text("target", encoding="utf-8")

            preview = preview_rename(RenameInput(source, "20260628", "ja00", "001"))

            self.assertEqual(preview.status, "conflict")

    def test_preview_batch_detects_duplicate_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first.pdf"
            second = root / "second.pdf"
            first.write_text("first", encoding="utf-8")
            second.write_text("second", encoding="utf-8")

            previews = preview_batch(
                [
                    RenameInput(first, "20260628", "ja00", "001"),
                    RenameInput(second, "20260628", "ja00", "001"),
                ]
            )

            self.assertEqual(previews[0].status, "ready")
            self.assertEqual(previews[1].status, "conflict")

    def test_apply_and_undo_rename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "raw.pdf"
            source.write_text("pdf", encoding="utf-8")
            history = HistoryStore(root / "history.sqlite3")
            preview = preview_rename(RenameInput(source, "20260628", "ja00", "001"))

            [target] = apply_batch_rename([preview], history)
            restored = undo_last_batch(history)

            self.assertFalse(target.exists())
            self.assertEqual(restored, [source])
            self.assertTrue(source.exists())

    def test_scan_files_filters_supported_extensions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.pdf").write_text("pdf", encoding="utf-8")
            (root / "b.txt").write_text("text", encoding="utf-8")
            nested = root / "nested"
            nested.mkdir()
            (nested / "c.jpg").write_text("image", encoding="utf-8")

            shallow = scan_files(root)
            recursive = scan_files(root, recursive=True)

            self.assertEqual([path.name for path in shallow], ["a.pdf"])
            self.assertEqual([path.name for path in recursive], ["a.pdf", "c.jpg"])

    def test_export_preview_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "raw.pdf"
            output = root / "preview.csv"
            source.write_text("pdf", encoding="utf-8")
            previews = preview_batch([RenameInput(source, "20260628", "ja00", "001")])

            export_preview_csv(previews, output)

            text = output.read_text(encoding="utf-8-sig")
            self.assertIn("source_path,target_path,target_name,status,message", text)
            self.assertIn("20260628_ja00_001.pdf", text)

    def test_apply_and_undo_batch_rename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first.pdf"
            second = root / "second.pdf"
            first.write_text("first", encoding="utf-8")
            second.write_text("second", encoding="utf-8")
            history = HistoryStore(root / "history.sqlite3")
            previews = preview_batch(
                [
                    RenameInput(first, "20260628", "ja00", "001"),
                    RenameInput(second, "20260628", "ja00", "002"),
                ]
            )

            changed = apply_batch_rename(previews, history)
            restored = undo_last_batch(history)

            self.assertEqual(len(changed), 2)
            self.assertFalse((root / "20260628_ja00_001.pdf").exists())
            self.assertFalse((root / "20260628_ja00_002.pdf").exists())
            self.assertEqual({path.name for path in restored}, {"first.pdf", "second.pdf"})
            self.assertTrue(first.exists())
            self.assertTrue(second.exists())

    def test_save_and_load_work_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "profiles.json"
            profile = WorkProfile(
                name="daily",
                date="20260712",
                media="ja00",
                page="003",
                rule="{MEDIA}-{DATE}-{PAGE}",
                recursive=True,
            )

            save_profile(path, profile)
            profiles = load_profiles(path)

            self.assertIn("daily", profiles)
            self.assertEqual(profiles["daily"].media, "ja00")
            self.assertEqual(profiles["daily"].rule, "{MEDIA}-{DATE}-{PAGE}")
            self.assertTrue(profiles["daily"].recursive)

    def test_file_assistant_interprets_korean_command(self) -> None:
        plan = interpret_file_command("2026-07-15 ja00 12부터 하위 폴더까지 정리해줘")

        self.assertEqual(plan.date, "20260715")
        self.assertEqual(plan.media, "ja00")
        self.assertEqual(plan.page, "012")
        self.assertTrue(plan.recursive)
        self.assertFalse(plan.needs_media)

    def test_file_assistant_requires_media_code(self) -> None:
        plan = interpret_file_command("20260715 문서 정리해줘")

        self.assertTrue(plan.needs_media)

    def test_purchase_evaluation_ranks_value_and_marks_evidence(self) -> None:
        target = ProductCandidate(
            name="Target",
            price=100_000,
            rating=4.2,
            review_count=40,
            warranty_months=12,
            suitability=3,
            is_target=True,
        )
        alternative = ProductCandidate(
            name="Alternative",
            price=80_000,
            rating=4.6,
            review_count=1_000,
            warranty_months=24,
            suitability=4,
        )

        assessments = evaluate_purchase([target, alternative])

        self.assertEqual(assessments[0].product.name, "Alternative")
        self.assertGreater(assessments[0].score, assessments[1].score)
        self.assertEqual(assessments[0].evidence_level, "high")

    def test_ai_advisor_requires_key_before_network_request(self) -> None:
        with patch.dict("src.nuri_assistant.classic.shopping.ai_advisor.os.environ", {}, clear=True):
            with patch("src.nuri_assistant.classic.shopping.ai_advisor.urlopen") as urlopen:
                with self.assertRaises(ShoppingAdvisorError):
                    advise_purchase("wireless headphones", [], api_key="")

        urlopen.assert_not_called()

    def test_ai_advisor_uses_web_search_and_disables_response_storage(self) -> None:
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self) -> bytes:
                return b'{"output":[{"content":[{"type":"output_text","text":"AI recommendation"}]}]}'

        product = ProductCandidate(name="Headphones", price=100_000, is_target=True)
        with patch("src.nuri_assistant.classic.shopping.ai_advisor.urlopen", return_value=FakeResponse()) as urlopen:
            advice = advise_purchase("Headphones comparison", [product], api_key="test-key")

        request = urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(advice.text, "AI recommendation")
        self.assertTrue(advice.used_web_search)
        self.assertFalse(payload["store"])
        self.assertEqual(payload["tools"], [{"type": "web_search"}])


class NoClobberTest(unittest.TestCase):
    def test_batch_rename_refuses_target_created_after_preview(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first, second = root / "first.pdf", root / "second.pdf"
            first.write_text("first", encoding="utf-8")
            second.write_text("second", encoding="utf-8")
            history = HistoryStore(root / "history.sqlite3")
            previews = preview_batch(
                [RenameInput(first, "20260628", "ja00", "001"), RenameInput(second, "20260628", "ja00", "002")]
            )
            # Another program creates the second target between preview and execution.
            (root / "20260628_ja00_002.pdf").write_text("someone else's file", encoding="utf-8")

            with self.assertRaises(RenameError):
                apply_batch_rename(previews, history)

            self.assertEqual((root / "20260628_ja00_002.pdf").read_text(encoding="utf-8"), "someone else's file")
            self.assertEqual(first.read_text(encoding="utf-8"), "first")
            self.assertEqual(second.read_text(encoding="utf-8"), "second")
            self.assertFalse((root / "20260628_ja00_001.pdf").exists())

    def test_undo_refuses_to_overwrite_recreated_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "raw.pdf"
            source.write_text("original", encoding="utf-8")
            history = HistoryStore(root / "history.sqlite3")
            apply_batch_rename(preview_batch([RenameInput(source, "20260628", "ja00", "001")]), history)
            source.write_text("new file with the old name", encoding="utf-8")

            with self.assertRaises(RenameError):
                undo_last_batch(history)

            self.assertEqual(source.read_text(encoding="utf-8"), "new file with the old name")
            self.assertTrue((root / "20260628_ja00_001.pdf").exists())


class FileToolsTest(unittest.TestCase):
    """The chat tools only preview; files change when the confirm card is approved."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.downloads = self.home / "Downloads"
        self.downloads.mkdir()
        for name in ("b_scan.pdf", "a_scan.pdf", "memo.txt"):
            (self.downloads / name).write_text("x", encoding="utf-8")
        self.history = HistoryStore(self.home / "history.sqlite3")
        self.tools = FileTools(self.history, home=lambda: self.home)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def names(self) -> list[str]:
        return sorted(path.name for path in self.downloads.iterdir())

    def test_preview_then_confirm_then_undo(self) -> None:
        result = self.tools.execute("rename_files", {"folder": "다운로드 폴더", "request": "20260715 ja00 3페이지부터 정리해줘"})
        self.assertTrue(result["ok"])
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["examples"][0], "a_scan.pdf → 20260715_ja00_003.pdf")
        self.assertEqual(self.names(), ["a_scan.pdf", "b_scan.pdf", "memo.txt"])  # nothing renamed yet

        action = self.tools.take_pending()[0]
        self.assertTrue(self.tools.owns(action))
        self.assertEqual((action.kind, action.when), ("rename", "다운로드 2개"))
        self.assertEqual(action.title, "a_scan.pdf → 20260715_ja00_003.pdf 외 1개")
        self.assertIn("2개", self.tools.confirm(action))
        self.assertEqual(self.names(), ["20260715_ja00_003.pdf", "20260715_ja00_004.pdf", "memo.txt"])

        self.assertTrue(self.tools.execute("undo_rename", {})["ok"])
        undo = self.tools.take_pending()[0]
        self.assertEqual(undo.kind, "undo")
        self.assertIn("2개", self.tools.confirm(undo))
        self.assertEqual(self.names(), ["a_scan.pdf", "b_scan.pdf", "memo.txt"])
        self.assertFalse(self.tools.execute("undo_rename", {})["ok"])

    def test_page_phrases(self) -> None:
        for request, page in (("ja00 3페이지부터", "003"), ("ja00 12쪽부터", "012"), ("ja00 p7", "007"),
                              ("20260715 ja00 1부터", "001"), ("20260715부터 ja00", "001")):
            self.assertEqual(interpret_file_command(request).page, page, request)

    def test_asks_instead_of_guessing(self) -> None:
        no_media = self.tools.execute("rename_files", {"folder": "다운로드", "request": "파일 이름 정리해줘"})
        self.assertFalse(no_media["ok"])
        self.assertIn("매체코드", no_media["error"])
        unknown = self.tools.execute("rename_files", {"folder": "회사 폴더", "request": "ja00"})
        self.assertFalse(unknown["ok"])
        self.assertEqual(self.tools.take_pending(), [])

    def test_file_changed_after_preview(self) -> None:
        self.tools.execute("rename_files", {"folder": str(self.downloads), "request": "ja00"})
        action = self.tools.take_pending()[0]
        (self.downloads / "b_scan.pdf").unlink()
        self.assertIn("바꾸지 못했어요", self.tools.confirm(action))
        self.assertEqual(self.names(), ["a_scan.pdf", "memo.txt"])  # the batch was rolled back

    def test_settings_rule_media_and_types(self) -> None:
        options = RenameOptions(rule="{YEAR}-{MONTH}-{DAY}_{PAGE}", extensions=(".txt",))
        tools = FileTools(self.history, lambda: options, home=lambda: self.home)
        result = tools.execute("rename_files", {"folder": "다운로드", "request": "20260715 정리해줘"})
        self.assertEqual(result["examples"], ["memo.txt → 2026-07-15_001.txt"])  # no media needed, only .txt

        options = RenameOptions(media="ja00")
        tools = FileTools(self.history, lambda: options, home=lambda: self.home)
        result = tools.execute("rename_files", {"folder": "다운로드", "request": "20260715 정리해줘"})
        self.assertEqual(result["examples"][0], "a_scan.pdf → 20260715_ja00_001.pdf")

        options = RenameOptions(rule="{DATE}_{MEDIA}")
        tools = FileTools(self.history, lambda: options, home=lambda: self.home)
        self.assertIn("페이지", tools.execute("rename_files", {"folder": "다운로드", "request": "ja00"})["error"])

    def test_skips_named_files_and_numbers_after_them(self) -> None:
        for page in ("001", "002"):
            (self.downloads / f"20260715_ja00_{page}.pdf").write_text("x", encoding="utf-8")
        result = self.tools.execute("rename_files", {"folder": "다운로드", "request": "20260715 ja00"})
        self.assertEqual(result["already_named"], 2)
        self.assertEqual(result["examples"], ["a_scan.pdf → 20260715_ja00_003.pdf", "b_scan.pdf → 20260715_ja00_004.pdf"])

        off = FileTools(self.history, lambda: RenameOptions(skip_named=False), home=lambda: self.home)
        self.assertEqual(off.execute("rename_files", {"folder": "다운로드", "request": "20260715 ja00"})["already_named"], 0)

    def test_rule_tokens(self) -> None:
        self.assertEqual(rule_from_korean("{날짜}_{매체}_{페이지}"), "{DATE}_{MEDIA}_{PAGE}")
        self.assertEqual(rule_to_korean("{YEAR}-{MONTH}-{DAY}_p{PAGE}"), "{연도}-{월}-{일}_p{페이지}")
        self.assertTrue(rule_pattern("{DATE}-{MEDIA}-p{PAGE}").fullmatch("20260715-JA00-p012"))
        self.assertFalse(rule_pattern("{DATE}_{MEDIA}_{PAGE}").fullmatch("scan_20260715"))
        for bad in ("{DATE}_{MEDIA}", "{날짜}_{PAGE}", "{DATE}_{PAGE}_{PAGE}x{FOO}"):
            with self.assertRaises(RenameError):
                validate_rule(bad)
        validate_rule(rule_from_korean("{연도}{월}{일}-{페이지}"))

    def test_resolve_folder(self) -> None:
        onedrive = self.home / "OneDrive" / "바탕 화면"
        onedrive.mkdir(parents=True)
        self.assertEqual(resolve_folder("바탕화면", self.home), onedrive)
        self.assertEqual(resolve_folder("Downloads", self.home), self.downloads)
        self.assertIsNone(resolve_folder("relative/path", self.home))
        self.assertIsInstance(RenameAction("undo", "x"), RenameAction)


if __name__ == "__main__":
    unittest.main()
