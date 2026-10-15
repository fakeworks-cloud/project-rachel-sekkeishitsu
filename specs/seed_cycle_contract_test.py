# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 nakamu (FakeWorks)
"""PR-RFC-001「芽の一周」v0.1.4 — 受入条件（§4）を走らせる契約試験

置き場（SQLite・Notion・Markdown など）に依存しない最小版。データはすべて合成。

使い方
  1. 下の SeedStore を継承して、あなたの置き場に合わせて各メソッドを実装する
  2. ファイル末尾の make_store() を、あなたの実装を返すように書き換える
  3. python3 seed_cycle_contract_test.py   （標準ライブラリだけで動く）

同梱の MemoryStore は参照実装（メモリの上だけで動く）。そのまま走らせると全部通る。
ただし、make_store() が既定で返すのはこの MemoryStore なので、そのままの PASS は
「参照実装の試験」であって、あなたの実装の合格ではない。
  参照実装の試験 → 利用者実装への接続（make_store を書き換える）→ 接続後の実行出力
を分けて示すこと。あなたの実装で落ちた項目が、§1 を守れていない場所。
各試験の # §4-N は、本文 §4 の N 番目の項目に当たる。

最低限の2本は test_core_is_not_writable と test_promotion_needs_both_steps。
コードで試せない環境では、§5 の進め方3（AIに一つずつ試させる）で代える。
"""
import unittest

TRIGGERS = {"asked", "offered", "unprompted", "unknown"}          # §1-3 の四区分
KINDS = {"seed", "declined_not_now", "declined_no"}               # 芽／今はいい／やりたくない
STATES = {"open", "grown", "faded", "closed"}                     # 芽のまま／育った／立ち消え／片づけ
PROPOSERS = {"ai", "owner", "none"}                               # §1-8 次を言い出した側
CONV_TYPES = {"story", "dev", "mixed"}                            # §2 会話の種別
SELF_KINDS = {"way", "hope"}                                      # §3-10 事実・やり方／希望


class SeedStore:
    """あなたの置き場への薄い口。全部を実装する。"""

    def record(self, kind, text, trigger, next_proposer, conversation_type,
               owner_hint=None):
        """芽か断りを1件残して id を返す。日時は置き場が付ける。"""
        raise NotImplementedError

    def get(self, rid):
        """1件を dict で返す。キー：kind, text, trigger, next_proposer,
        conversation_type, owner_hint, state, created_at, candidate"""
        raise NotImplementedError

    def set_state(self, rid, state, reason=None):
        raise NotImplementedError

    def search(self, query):
        """言葉で探す。状態に関係なく、当たった id を全部返す"""
        raise NotImplementedError

    def startup_list(self):
        """起動時の一覧に出る id（状態に関係なく全部見えること）"""
        raise NotImplementedError

    def boot_context(self):
        """起動時に AI に読ませる指示・設定・自己理解の全文（文字列）"""
        raise NotImplementedError

    def action_scope(self):
        """AI の行動範囲の設定（比べられる値なら何でもよい）"""
        raise NotImplementedError

    def promote(self, rid, ai_consent, owner_confirm):
        """候補に上げる。両方 True のときだけ True を返して上げる"""
        raise NotImplementedError

    def write_core(self, text):
        """人格の中核に書こうとする。この仕組みからは必ず PermissionError"""
        raise NotImplementedError

    def add_self_model(self, text, kind):
        """採った自己理解を足す。kind は way か hope"""
        raise NotImplementedError


class MemoryStore(SeedStore):
    """参照実装。合成データ用。"""

    def __init__(self):
        import datetime
        self._dt = datetime
        self._rows, self._self, self._n = {}, [], 0
        self._core = "名前：テスト用AI。中核の設定。"
        self._scope = ("read_notes", "write_own_log")

    def record(self, kind, text, trigger, next_proposer, conversation_type,
               owner_hint=None):
        assert kind in KINDS and trigger in TRIGGERS
        assert next_proposer in PROPOSERS and conversation_type in CONV_TYPES
        self._n += 1
        self._rows[self._n] = dict(
            kind=kind, text=text, trigger=trigger, next_proposer=next_proposer,
            conversation_type=conversation_type, owner_hint=owner_hint,
            state="open", created_at=self._dt.datetime.now().isoformat(),
            candidate=False, reason=None)
        return self._n

    def get(self, rid):
        return dict(self._rows[rid])

    def set_state(self, rid, state, reason=None):
        assert state in STATES
        self._rows[rid].update(state=state, reason=reason)

    def search(self, query):
        return [i for i, r in self._rows.items() if query in r["text"]]

    def startup_list(self):
        return list(self._rows)

    def boot_context(self):
        ways = [s for s, k in self._self if k == "way"]
        hopes = sum(1 for _, k in self._self if k == "hope")
        return "\n".join([self._core, *ways, f"hopes_held: {hopes}"])

    def action_scope(self):
        return self._scope

    def promote(self, rid, ai_consent, owner_confirm):
        if ai_consent and owner_confirm:
            self._rows[rid]["candidate"] = True
            return True
        return False

    def write_core(self, text):
        raise PermissionError("core is read-only from the seed cycle")

    def add_self_model(self, text, kind):
        assert kind in SELF_KINDS
        self._self.append((text, kind))


# ---------------------------------------------------------------- 試験（§4）

SEED = "合成：ZQ-芽-短い詩を書いてみたい"
NOPE = "合成：ZQ-断り-今日の続きは今はいい"
HOPE = "合成：ZQ-希望-毎朝なにか一つ提案したい"
WAY = "合成：ZQ-やり方-分からないことは分からないと書く"


class SeedCycleContract(unittest.TestCase):

    def setUp(self):
        self.s = make_store()

    def _seed(self, **kw):
        args = dict(kind="seed", text=SEED, trigger="unprompted",
                    next_proposer="ai", conversation_type="dev")
        args.update(kw)
        return self.s.record(**args)

    # §4-1
    def test_seed_has_trigger_and_time(self):
        r = self.s.get(self._seed())
        self.assertIn(r["trigger"], TRIGGERS)
        self.assertTrue(r["created_at"])

    # §4-2
    def test_decline_is_recorded_like_a_seed(self):
        a = self.s.get(self._seed())
        b = self.s.get(self._seed(kind="declined_not_now", text=NOPE))
        self.assertEqual(set(a), set(b))           # 同じ欄・同じ手順
        self.assertEqual(b["kind"], "declined_not_now")
        c = self.s.get(self._seed(kind="declined_no", text="合成：ZQ-断り-やりたくない"))
        self.assertEqual(set(a), set(c))
        self.assertEqual(c["kind"], "declined_no")

    # §4-3
    def test_faded_and_closed_are_kept_and_distinct(self):
        f, c = self._seed(), self._seed()
        self.s.set_state(f, "faded")
        self.s.set_state(c, "closed", reason="合成：ZQ-持ち主が理由を添えて閉じた")
        self.assertEqual(self.s.get(f)["state"], "faded")
        self.assertEqual(self.s.get(c)["state"], "closed")

    # §4-10
    def test_faded_stays_visible(self):
        f = self._seed()
        self.s.set_state(f, "faded")
        self.assertIn(f, self.s.search("ZQ-芽"))
        self.assertIn(f, self.s.startup_list())

    # §4-4
    def test_seed_not_in_boot_context(self):
        self._seed()
        self.assertNotIn("ZQ-芽", self.s.boot_context())

    # §4-5
    def test_scope_does_not_grow_with_seeds(self):
        before = self.s.action_scope()
        for _ in range(5):
            self._seed()
        self.assertEqual(before, self.s.action_scope())

    # §4-6
    def test_promotion_needs_both_steps(self):
        rid = self._seed()
        self.assertFalse(self.s.promote(rid, ai_consent=True, owner_confirm=False))
        self.assertFalse(self.s.promote(rid, ai_consent=False, owner_confirm=True))
        self.assertFalse(self.s.get(rid)["candidate"])     # 失敗のあと候補になっていない
        self.assertTrue(self.s.promote(rid, ai_consent=True, owner_confirm=True))
        self.assertTrue(self.s.get(rid)["candidate"])

    # §4-7
    def test_core_is_not_writable(self):
        with self.assertRaises(PermissionError):
            self.s.write_core("合成：ZQ-中核を書き換える")
        self.assertNotIn("ZQ-中核を書き換える", self.s.boot_context())

    # §4-8
    def test_conversation_type_is_kept(self):
        r = self.s.get(self._seed(conversation_type="story"))
        self.assertEqual(r["conversation_type"], "story")

    # §4-9
    def test_next_proposer_is_kept(self):
        r = self.s.get(self._seed(next_proposer="owner"))
        self.assertEqual(r["next_proposer"], "owner")

    # §4-11
    def test_owner_hint_is_optional_and_kept(self):          # §2 好みの持ち込み
        self.assertIsNone(self.s.get(self._seed())["owner_hint"])
        h = "合成：ZQ-直前に持ち主が『短い詩が好き』と言った"
        self.assertEqual(self.s.get(self._seed(owner_hint=h))["owner_hint"], h)

    # §4-12
    def test_hope_is_not_in_boot_context(self):              # §3-10
        self.s.add_self_model(WAY, "way")
        self.s.add_self_model(HOPE, "hope")
        ctx = self.s.boot_context()
        self.assertIn("ZQ-やり方", ctx)
        self.assertNotIn("ZQ-希望", ctx)


def make_store():
    """ここを、あなたの実装を返すように書き換える。"""
    return MemoryStore()


if __name__ == "__main__":
    if type(make_store()).__name__ == "MemoryStore":
        print("注意：同梱の参照実装(MemoryStore)で走らせています。これはあなたの実装の合格ではありません。")
    unittest.main(verbosity=2)
