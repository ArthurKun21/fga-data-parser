import json
import re

import orjson
import pytest

from fgo_translate import fgo_translate_pb2
from fgo_translate.atlas import (
    build_atlas_entries,
    collect_translatable_texts,
    collect_used_texts,
)
from fgo_translate.cli import main
from fgo_translate.pb import translations_to_bytes
from fgo_translate.pipeline import (
    Translation,
    apply_overwrite_translations,
    build_translations,
    load_overwrite_translations,
    overwrite_translations_to_json,
    translations_to_json,
)


def write_chaldea_data(tmp_path, *, patch=None) -> None:
    mappings = tmp_path / "chaldea-data" / "mappings"
    mappings.mkdir(parents=True)
    (mappings / "svt_names.json").write_bytes(
        orjson.dumps(
            {
                "マシュ・キリエライト": {
                    "JP": None,
                    "CN": "玛修·基列莱特",
                    "NA": "Mash Kyrielight",
                    "KR": None,
                },
                "魔\ue000セイバー": {"JP": None, "NA": "Fou Saber"},
                # The correct community translation the Aozaki-Aoko incident
                # stole: the buggy pairing let Atlas claim every region first.
                "フランチェスカ・プレラーティ": {
                    "JP": None,
                    "CN": "弗兰切斯卡·普勒拉蒂",
                    "NA": "Francesca Prélat",
                },
            }
        )
    )
    # Same key as svt_names; only fills the region svt_names left empty.
    (mappings / "entity_names.json").write_bytes(
        orjson.dumps({"マシュ・キリエライト": {"KR": "매슈"}})
    )
    (mappings / "ce_names.json").write_bytes(
        orjson.dumps({"2030年の欠片": {"JP": None, "NA": "A Fragment of 2030"}})
    )
    (mappings / "mc_names.json").write_bytes(
        orjson.dumps(
            {
                "カルデア学園制服": {"JP": None, "NA": "Chaldea Academy Uniform"},
                "魔術礼装・カルデア": {"NA": "Chaldea Uniform", "KR": "칼데아 유니폼"},
            }
        )
    )
    (mappings / "skill_names.json").write_bytes(
        orjson.dumps(
            {
                "スキル名": {"JP": None, "NA": "Skill Name"},
                # Conflicts with the cross-referenced Atlas text on purpose.
                "カリスマ B": {"NA": "Chaldea Charisma", "CN": "カリスマCN"},
            }
        )
    )
    (mappings / "skill_detail.json").write_bytes(
        orjson.dumps(
            {"自身の攻撃力をアップ[{0}](3ターン)": {"JP": None, "NA": "Increase ATK [{0}]"}}
        )
    )
    (mappings / "buff_names.json").write_bytes(
        orjson.dumps({"無敵状態": {"JP": None, "NA": "Invincibility"}})
    )
    # funcPopupText strings the parser copies into script-function payloads.
    (mappings / "func_popuptext.json").write_bytes(
        orjson.dumps({"宝具タイプチェンジ": {"JP": None, "NA": "NP Type Change"}})
    )
    # misc.json is sectioned; only the JP-text-keyed skill popup sections are
    # folded in, identifier-keyed ones like Function stay out.
    (mappings / "misc.json").write_bytes(
        orjson.dumps(
            {
                "SelectAddInfo": {
                    "入れ替えるか選択してください": {"JP": None, "CN": "请选择是否替换灵基"},
                    "入れ替えない": {"JP": None, "CN": "不替换"},
                },
                "selectTreasureDeviceInfo": {"攻撃タイプ": {"JP": None, "NA": "Attack Type"}},
                "Function": {
                    "ifPrevFuncSucceed": {
                        "JP": "前の効果が成功時",
                        "NA": "If previous func succeeds",
                    }
                },
            }
        )
    )
    for empty_table in ("td_names", "td_detail", "buff_detail"):
        (mappings / f"{empty_table}.json").write_bytes(orjson.dumps({}))
    if patch is not None:
        dist = tmp_path / "chaldea-data" / "dist"
        dist.mkdir()
        (dist / "mappingPatch.json").write_bytes(orjson.dumps(patch))


def test_build_translations(tmp_path) -> None:
    write_chaldea_data(
        tmp_path,
        patch={
            "svt_names": {"マシュ・キリエライト": {"NA": "Mash (Patched)"}},
            "ce_names": {"新礼装": {"NA": "New CE"}},
            "quest_names": {"クエスト": {"NA": "Ignored Section"}},
        },
    )

    translations = build_translations(tmp_path / "chaldea-data")

    mash = translations["マシュ・キリエライト"]
    assert mash.jp == "マシュ・キリエライト"
    assert mash.na == "Mash (Patched)"
    assert mash.cn == "玛修·基列莱特"
    assert mash.kr == "매슈"
    assert translations["魔{jin}セイバー"].na == "Fou Saber"
    assert translations["2030年の欠片"].na == "A Fragment of 2030"
    assert translations["カルデア学園制服"].na == "Chaldea Academy Uniform"
    assert translations["スキル名"].na == "Skill Name"
    assert translations["自身の攻撃力をアップ[{0}](3ターン)"].na == "Increase ATK [{0}]"
    assert translations["新礼装"].na == "New CE"
    # Patch sections outside TABLE_NAMES are ignored.
    assert "クエスト" not in translations


def test_missing_patch_file_is_tolerated(tmp_path) -> None:
    write_chaldea_data(tmp_path)

    translations = build_translations(tmp_path / "chaldea-data")

    assert translations["マシュ・キリエライト"].na == "Mash Kyrielight"


def test_popup_text_tables_merge(tmp_path) -> None:
    write_chaldea_data(tmp_path)

    translations = build_translations(tmp_path / "chaldea-data")

    assert translations["宝具タイプチェンジ"].na == "NP Type Change"
    assert translations["入れ替えるか選択してください"].cn == "请选择是否替换灵基"
    assert translations["攻撃タイプ"].na == "Attack Type"
    # Identifier-keyed sections are not game text and stay out.
    assert "ifPrevFuncSucceed" not in translations


def test_patch_updates_popup_tables(tmp_path) -> None:
    write_chaldea_data(
        tmp_path,
        patch={
            "func_popuptext": {"宝具タイプチェンジ": {"NA": "Patched Type Change"}},
            "misc": {"SelectAddInfo": {"入れ替えない": {"CN": "补丁替换"}}},
        },
    )

    translations = build_translations(tmp_path / "chaldea-data")

    assert translations["宝具タイプチェンジ"].na == "Patched Type Change"
    assert translations["入れ替えない"].cn == "补丁替换"


def test_tables_only_fill_gaps_but_patch_wins(tmp_path) -> None:
    write_chaldea_data(
        tmp_path,
        patch={"svt_names": {"マシュ・キリエライト": {"KR": "매슈 패치"}}},
    )

    translations = build_translations(tmp_path / "chaldea-data")

    mash = translations["マシュ・キリエライト"]
    # entity_names filled kr first, but the patch overrides it.
    assert mash.kr == "매슈 패치"
    assert mash.na == "Mash Kyrielight"


def test_translations_to_json_shape() -> None:
    translations = {
        "b": Translation(jp="b", na="B"),
        "a": Translation(jp="a"),
    }

    json_data = translations_to_json(translations)

    assert list(json_data) == ["translations"]
    assert list(json_data["translations"]) == ["a", "b"]
    assert json_data["translations"]["a"] == {"jp": "a"}
    assert json_data["translations"]["b"] == {"jp": "b", "na": "B"}


def test_proto_round_trip(tmp_path) -> None:
    write_chaldea_data(tmp_path)
    translations = build_translations(tmp_path / "chaldea-data")

    parsed = fgo_translate_pb2.FgoTranslate.FromString(translations_to_bytes(translations))

    mash = parsed.translations["マシュ・キリエライト"]
    assert mash.jp == "マシュ・キリエライト"
    assert mash.na == "Mash Kyrielight"
    assert mash.kr == "매슈"
    fou = parsed.translations["魔{jin}セイバー"]
    assert fou.na == "Fou Saber"
    assert fou.cn == ""  # unset region serializes as the empty string
    assert len(parsed.translations) == len(translations)


def test_cli_writes_both_outputs(tmp_path) -> None:
    write_chaldea_data(tmp_path)

    exit_code = main(
        [
            "--atlas-data",
            str(tmp_path / "no-parsed-data"),
            "--chaldea-data",
            str(tmp_path / "chaldea-data"),
            "--output-dir",
            str(tmp_path),
            "--overwrite-translations",
            str(tmp_path / "overwrite_translations.json"),
        ]
    )

    assert exit_code == 0
    json_data = json.loads((tmp_path / "fgo_translate.json").read_text())
    assert list(json_data) == ["translations"]
    parsed = fgo_translate_pb2.FgoTranslate.FromString((tmp_path / "fgo_translate.pb").read_bytes())
    assert len(parsed.translations) == len(json_data["translations"])


def write_atlas_data(tmp_path) -> None:
    """Parser-shaped per-region outputs; KR has no output to test missing regions."""
    data_dir = tmp_path / "atlas-data"
    data_dir.mkdir()

    def servant(*, name: str, skills: list, nps: list, append_passives: list) -> dict:
        return {
            "id": 100100,
            "collection_no": 2,
            "name": name,
            "skills": skills,
            "nps": nps,
            "append_passives": append_passives,
        }

    jp_skills = [
        {
            "id": 1,
            "num": 1,
            "name": "カリスマ B",
            "detail": "味方全体の攻撃力をアップ[{0}](3ターン)",
            "icon": "https://example.test/SkillIcons/skill_1.png",
            "functions": [
                {
                    "target": "Choice2",
                    "choice2": {
                        "detail": "入れ替えるか選択してください",
                        "option_a": "入れ替えない",
                        "option_b": "入れ替える",
                    },
                }
            ],
        },
        # A fresh JP upgrade the other regions have not received yet.
        {"id": 2, "num": 1, "name": "強化カリスマ A", "detail": "強化版[{0}]", "functions": []},
    ]
    jp_nps = [
        {
            "id": 11,
            "num": 1,
            "name": "約束された勝利の剣",
            "detail": "敵全体に非常に強力な攻撃[{0}]",
        },
        # A fresh JP NP the other regions have not received yet.
        {"id": 12, "num": 2, "name": "約束された勝利の剣・改", "detail": "強化版宝具詳細[{0}]"},
    ]
    na_skills = [
        {
            "id": 1,
            "num": 1,
            "name": "Charisma B",
            "detail": "Increase ATK for all allies [{0}]",
            "functions": [
                {
                    "target": "Choice2",
                    "choice2": {"detail": "Choose", "option_a": "Keep", "option_b": "Swap"},
                }
            ],
        }
    ]
    tw_skills = [
        # Same slot (num 1) under a different id: exercises the num fallback.
        {
            "id": 999,
            "num": 1,
            "name": "カリスマ・プラス",
            "detail": "TW版詳細[{0}]",
            "functions": [],
        }
    ]

    servants = {
        "": [
            servant(
                name="Artoria Pendragon (Saber)",
                skills=jp_skills,
                nps=jp_nps,
                append_passives=[
                    {
                        "num": 1,
                        "skill": {
                            "id": 21,
                            "num": 0,
                            "name": "対魔力 C",
                            "original_name": "対魔力",
                            "detail": "自身の弱体耐性をアップ[{0}]",
                        },
                    }
                ],
            ),
            # Private-use characters get normalized like every other source.
            {
                "id": 2,
                "collection_no": 3,
                "name": "魔\ue000セイバー",
                "skills": [],
                "nps": [],
                "append_passives": [],
            },
            # A JP-only servant: no region has it, so only Chaldea can
            # translate it — pruning must keep that row.
            {
                "id": 3,
                "collection_no": 4,
                "name": "マシュ・キリエライト",
                "skills": [],
                "nps": [],
                "append_passives": [],
            },
            # The real shape of the Aozaki-Aoko incident: two JP servants
            # share collection_no 0 and only Aoko exists in NA.
            {
                "id": 505700,
                "collection_no": 0,
                "name": "フランチェスカ・プレラーティ",
                "skills": [],
                "nps": [],
                "append_passives": [],
            },
            {
                "id": 2501500,
                "collection_no": 0,
                "name": "蒼崎青子",
                "skills": [],
                "nps": [],
                "append_passives": [],
            },
        ],
        ".na": [
            servant(
                # The official NA text keeps "Altria"; values are never renamed.
                name="Altria Pendragon",
                skills=na_skills,
                nps=[
                    {
                        "id": 11,
                        "num": 1,
                        "name": "Excalibur",
                        "detail": "Deal significant damage to all enemies.",
                    }
                ],
                append_passives=[
                    {
                        "num": 1,
                        "skill": {
                            "id": 21,
                            "num": 0,
                            "name": "Magic Resistance C",
                            "original_name": "Magic Resistance",
                            "detail": "Increase debuff resistance [{0}]",
                        },
                    }
                ],
            ),
            {
                "id": 2,
                "collection_no": 3,
                "name": "Fou Saber",
                "skills": [],
                "nps": [],
                "append_passives": [],
            },
            {
                "id": 2501500,
                "collection_no": 0,
                "name": "Aozaki Aoko",
                "skills": [],
                "nps": [],
                "append_passives": [],
            },
        ],
        # CN only translates the servant name so far.
        ".cn": [servant(name="阿尔托莉雅·潘德拉贡", skills=[], nps=[], append_passives=[])],
        ".tw": [
            servant(
                # The fullwidth stop is the official TW text, not a typo.
                name="阿爾托莉亞．潘德拉剛",  # noqa: RUF001
                skills=tw_skills,
                nps=[{"id": 888, "num": 1, "name": "勝利の剣TW", "detail": "TW版宝具詳細"}],
                append_passives=[],
            )
        ],
    }
    for suffix, entries in servants.items():
        (data_dir / f"servant_data{suffix}.json").write_bytes(orjson.dumps(entries))

    (data_dir / "mystic_code_data.json").write_bytes(
        orjson.dumps(
            [
                {
                    "id": 1,
                    "name": "魔術礼装･カルデア",
                    "skills": [
                        {
                            "id": 980001,
                            "num": 0,
                            "name": "応急手当",
                            "detail": "味方単体のHPを大回復[{0}]",
                            "functions": [],
                        }
                    ],
                }
            ]
        )
    )
    (data_dir / "mystic_code_data.na.json").write_bytes(
        orjson.dumps(
            [
                {
                    "id": 1,
                    "name": "Chaldea Combat Uniform",
                    "skills": [
                        {
                            "id": 980001,
                            "num": 0,
                            "name": "First Aid",
                            "detail": "Recover one ally's HP [{0}]",
                            "functions": [],
                        }
                    ],
                }
            ]
        )
    )

    craft_essences = {
        "": [
            {
                "id": 9300010,
                "collection_no": 191,
                "name": "星の王冠",
                "original_name": "旧星の王冠",
                "skills": [
                    {
                        "id": 990338,
                        "name": "王冠の輝き",
                        "original_name": "王冠の輝き",
                        "detail": "自身のクリティカル威力をアップする",
                    }
                ],
            }
        ],
        ".na": [
            {
                "id": 9300010,
                "collection_no": 191,
                "name": "Crown of the Star",
                "original_name": "Old Star Crown",
                "skills": [
                    {
                        "id": 990338,
                        "name": "Radiant Crown",
                        "original_name": "Radiant Crown",
                        "detail": "Increase own critical strength.",
                    }
                ],
            }
        ],
    }
    for suffix, entries in craft_essences.items():
        (data_dir / f"craft_essence_data{suffix}.json").write_bytes(orjson.dumps(entries))


def test_build_atlas_entries(tmp_path) -> None:
    write_atlas_data(tmp_path)

    entries = build_atlas_entries(tmp_path / "atlas-data")

    # Mutated JP keys land verbatim so consumer lookups against the parser
    # data hit them; private-use chars normalize like the Chaldea keys.
    assert entries["Artoria Pendragon (Saber)"] == {
        "cn": "阿尔托莉雅·潘德拉贡",
        "na": "Altria Pendragon",
        "tw": "阿爾托莉亞．潘德拉剛",  # noqa: RUF001
    }
    assert entries["魔{jin}セイバー"] == {"na": "Fou Saber"}

    # NA matches by shared skill id, TW by num fallback; KR has no output.
    assert entries["カリスマ B"] == {"na": "Charisma B", "tw": "カリスマ・プラス"}
    assert entries["味方全体の攻撃力をアップ[{0}](3ターン)"] == {
        "na": "Increase ATK for all allies [{0}]",
        "tw": "TW版詳細[{0}]",
    }
    # The JP-only upgrade matches nothing: no id in the other regions and
    # its num slot is already taken.
    assert "強化カリスマ A" not in entries

    assert entries["入れ替えるか選択してください"] == {"na": "Choose"}
    assert entries["入れ替えない"] == {"na": "Keep"}
    assert entries["約束された勝利の剣"] == {"na": "Excalibur", "tw": "勝利の剣TW"}
    assert entries["敵全体に非常に強力な攻撃[{0}]"] == {
        "na": "Deal significant damage to all enemies.",
        "tw": "TW版宝具詳細",
    }
    # The JP-only NP pairs with nothing, like the JP-only skill.
    assert "強化版宝具詳細[{0}]" not in entries
    assert entries["対魔力 C"] == {"na": "Magic Resistance C"}
    assert entries["対魔力"] == {"na": "Magic Resistance"}
    assert entries["自身の弱体耐性をアップ[{0}]"] == {"na": "Increase debuff resistance [{0}]"}

    assert entries["魔術礼装･カルデア"] == {"na": "Chaldea Combat Uniform"}
    assert entries["応急手当"] == {"na": "First Aid"}
    assert entries["星の王冠"] == {"na": "Crown of the Star"}
    assert entries["旧星の王冠"] == {"na": "Old Star Crown"}
    assert entries["王冠の輝き"] == {"na": "Radiant Crown"}

    # The collection-no-0 incident: JP Francesca has no NA counterpart, so the
    # Atlas pass records nothing for her (Chaldea fills the name later), while
    # JP Aoko pairs with NA Aoko by the shared id — never by the colliding
    # collection number.
    assert "フランチェスカ・プレラーティ" not in entries
    assert entries["蒼崎青子"] == {"na": "Aozaki Aoko"}

    assert all("kr" not in regions for regions in entries.values())


def test_build_atlas_entries_without_jp_data(tmp_path) -> None:
    assert build_atlas_entries(tmp_path / "missing") == {}


def test_collection_number_fallback_for_id_drift(tmp_path) -> None:
    """A region may host an entity under a different id; the shared non-zero
    collection number still pairs it, while collection_no 0 never does."""
    data_dir = tmp_path / "atlas-data"
    data_dir.mkdir()

    def servant(entity_id: int, collection_no: int, name: str) -> dict:
        return {
            "id": entity_id,
            "collection_no": collection_no,
            "name": name,
            "skills": [],
            "nps": [],
            "append_passives": [],
        }

    (data_dir / "servant_data.json").write_bytes(
        orjson.dumps(
            [
                # NA still hosts collection 7 under the older id 200.
                servant(100, 7, "改名前"),
                # The shared id pairs despite differing collection numbers.
                servant(104, 9, "先着順"),
                # Unnumbered servants must never pair on collection_no 0.
                servant(102, 0, "無番号"),
            ]
        )
    )
    (data_dir / "servant_data.na.json").write_bytes(
        orjson.dumps(
            [
                servant(200, 7, "Renamed"),
                servant(104, 99, "Same Id Different Number"),
                servant(103, 0, "Unnumbered NA"),
            ]
        )
    )

    entries = build_atlas_entries(data_dir)

    assert entries["改名前"] == {"na": "Renamed"}
    assert entries["先着順"] == {"na": "Same Id Different Number"}
    assert "無番号" not in entries


def test_collection_no_zero_servants_fill_from_chaldea(tmp_path) -> None:
    write_atlas_data(tmp_path)
    write_chaldea_data(tmp_path)

    translations = build_translations(
        tmp_path / "chaldea-data",
        atlas_entries=build_atlas_entries(tmp_path / "atlas-data"),
        used_texts=collect_used_texts(tmp_path / "atlas-data"),
    )

    # Francesca pairs with no region, so Chaldea's community translation
    # survives instead of a wrong servant's official text.
    francesca = translations["フランチェスカ・プレラーティ"]
    assert francesca.na == "Francesca Prélat"
    assert francesca.cn == "弗兰切斯卡·普勒拉蒂"
    assert translations["蒼崎青子"].na == "Aozaki Aoko"


def test_atlas_wins_chaldea_fills_patch_wins_last(tmp_path) -> None:
    write_atlas_data(tmp_path)
    write_chaldea_data(
        tmp_path,
        patch={
            "skill_detail": {"味方全体の攻撃力をアップ[{0}](3ターン)": {"NA": "Patched ATK"}},
            "svt_names": {"魔\ue000セイバー": {"TW": "Fou Saber TW"}},
        },
    )

    translations = build_translations(
        tmp_path / "chaldea-data", atlas_entries=build_atlas_entries(tmp_path / "atlas-data")
    )

    # Official Atlas text beats the conflicting Chaldea value, which still
    # fills the region Atlas lacks (CN has no skills in the parsed output).
    charisma = translations["カリスマ B"]
    assert charisma.na == "Charisma B"
    assert charisma.cn == "カリスマCN"
    # The patch wins even over the Atlas text.
    assert translations["味方全体の攻撃力をアップ[{0}](3ターン)"].na == "Patched ATK"
    # A patch on an Atlas key propagates to its Chaldea spelling too.
    assert translations["魔{jin}セイバー"].tw == "Fou Saber TW"
    # Chaldea-only keys survive next to the Atlas keys.
    assert translations["マシュ・キリエライト"].na == "Mash Kyrielight"
    assert translations["マシュ・キリエライト"].kr == "매슈"


def test_middle_dot_keys_alias_both_spellings(tmp_path) -> None:
    write_atlas_data(tmp_path)  # halfwidth ･ key from the parser output
    write_chaldea_data(tmp_path)  # fullwidth ・ key from the Chaldea table

    translations = build_translations(
        tmp_path / "chaldea-data", atlas_entries=build_atlas_entries(tmp_path / "atlas-data")
    )

    halfwidth = translations["魔術礼装･カルデア"]
    fullwidth = translations["魔術礼装・カルデア"]
    # Atlas wins for NA on both spellings; the Chaldea key fills KR through
    # the alias. (The jp fields differ: each spelling keeps its own key.)
    assert halfwidth.na == "Chaldea Combat Uniform"
    assert halfwidth.kr == "칼데아 유니폼"
    assert fullwidth.na == halfwidth.na
    assert fullwidth.kr == halfwidth.kr


def test_collect_used_texts(tmp_path) -> None:
    write_atlas_data(tmp_path)

    used = collect_used_texts(tmp_path / "atlas-data")

    assert "Artoria Pendragon (Saber)" in used
    assert "カリスマ B" in used
    assert "味方全体の攻撃力をアップ[{0}](3ターン)" in used
    assert "魔術礼装･カルデア" in used
    # Values normalize like the table keys.
    assert "魔{jin}セイバー" in used
    assert collect_used_texts(tmp_path / "missing") is None


def test_collect_translatable_texts(tmp_path) -> None:
    write_atlas_data(tmp_path)

    texts = collect_translatable_texts(tmp_path / "atlas-data")

    assert texts is not None
    # Skill names/details, script payload texts, NP names and details, append
    # passives, mystic code and craft essence fields.
    assert {
        "Artoria Pendragon (Saber)",
        "カリスマ B",
        "味方全体の攻撃力をアップ[{0}](3ターン)",
        "入れ替えるか選択してください",
        "入れ替えない",
        "入れ替える",
        "強化カリスマ A",
        "強化版[{0}]",
        "約束された勝利の剣",
        "敵全体に非常に強力な攻撃[{0}]",
        "約束された勝利の剣・改",
        "強化版宝具詳細[{0}]",
        "対魔力 C",
        "対魔力",
        "自身の弱体耐性をアップ[{0}]",
        "魔{jin}セイバー",
        "マシュ・キリエライト",
        "フランチェスカ・プレラーティ",
        "蒼崎青子",
        "魔術礼装･カルデア",
        "応急手当",
        "味方単体のHPを大回復[{0}]",
        "星の王冠",
        "旧星の王冠",
        "王冠の輝き",
        "自身のクリティカル威力をアップする",
    } <= texts
    # Non-translatable leaves stay out, unlike collect_used_texts.
    assert "https://example.test/SkillIcons/skill_1.png" not in texts
    assert "https://example.test/SkillIcons/skill_1.png" in collect_used_texts(
        tmp_path / "atlas-data"
    )


def test_collect_translatable_texts_without_jp_data(tmp_path) -> None:
    assert collect_translatable_texts(tmp_path / "missing") is None


def test_unused_keys_are_pruned(tmp_path) -> None:
    write_atlas_data(tmp_path)
    write_chaldea_data(tmp_path)

    translations = build_translations(
        tmp_path / "chaldea-data",
        atlas_entries=build_atlas_entries(tmp_path / "atlas-data"),
        used_texts=collect_used_texts(tmp_path / "atlas-data"),
    )

    # Used texts survive — including Chaldea-only rows for them (the JP-only
    # servant) — while rows the data files never show are dropped, along with
    # the alias spelling of the used key.
    assert "カリスマ B" in translations
    assert translations["マシュ・キリエライト"].na == "Mash Kyrielight"
    assert translations["マシュ・キリエライト"].kr == "매슈"
    assert translations["魔{jin}セイバー"].na == "Fou Saber"
    assert "無敵状態" not in translations  # buff_names row
    assert "スキル名" not in translations  # skill_names row
    assert "2030年の欠片" not in translations  # ce_names row
    assert "自身の攻撃力をアップ[{0}](3ターン)" not in translations  # skill_detail row
    assert "魔術礼装・カルデア" not in translations  # alias spelling


def test_cli_prunes_to_used_texts(tmp_path) -> None:
    write_atlas_data(tmp_path)
    write_chaldea_data(tmp_path)

    exit_code = main(
        [
            "--atlas-data",
            str(tmp_path / "atlas-data"),
            "--chaldea-data",
            str(tmp_path / "chaldea-data"),
            "--output-dir",
            str(tmp_path),
            "--overwrite-translations",
            str(tmp_path / "overwrite_translations.json"),
        ]
    )

    assert exit_code == 0
    json_data = json.loads((tmp_path / "fgo_translate.json").read_text())
    assert "カリスマ B" in json_data["translations"]
    assert "スキル名" not in json_data["translations"]
    assert "魔術礼装・カルデア" not in json_data["translations"]


def test_required_texts_add_sourceless_keys(tmp_path) -> None:
    write_chaldea_data(tmp_path)

    translations = build_translations(
        tmp_path / "chaldea-data",
        required_texts={"マシュ・キリエライト", "JPだけのスキル詳細"},
    )

    # A used text no source covers is present but translation-less, and the
    # JSON output keeps it as a jp-only entry for the consumer's fallback.
    sourceless = translations["JPだけのスキル詳細"]
    assert sourceless.jp == "JPだけのスキル詳細"
    assert sourceless.cn is None
    assert sourceless.tw is None
    assert sourceless.na is None
    assert sourceless.kr is None
    json_data = translations_to_json(translations)
    assert json_data["translations"]["JPだけのスキル詳細"] == {"jp": "JPだけのスキル詳細"}
    # A key a source covers is untouched.
    assert translations["マシュ・キリエライト"].na == "Mash Kyrielight"


def test_required_texts_none_adds_nothing(tmp_path) -> None:
    write_chaldea_data(tmp_path)

    translations = build_translations(tmp_path / "chaldea-data")

    assert "JPだけのスキル詳細" not in translations


def test_sourceless_key_queues_into_overwrite_and_fills(tmp_path) -> None:
    write_chaldea_data(tmp_path)
    overwrite_path = tmp_path / "overwrite_translations.json"
    overwrite_path.write_bytes(
        orjson.dumps({"translations": {"JPだけのスキル詳細": {"cn": "仅JP的技能详情"}}})
    )

    translations = build_translations(
        tmp_path / "chaldea-data", required_texts={"JPだけのスキル詳細"}
    )
    updated = apply_overwrite_translations(
        translations, load_overwrite_translations(overwrite_path)
    )

    # The fill reaches the translation-less entry; the queue keeps the key
    # for the regions still missing, so the next rebuild reapplies it.
    assert translations["JPだけのスキル詳細"].cn == "仅JP的技能详情"
    assert updated["JPだけのスキル詳細"] == {
        "cn": "仅JP的技能详情",
        "tw": None,
        "na": None,
        "kr": None,
    }


def test_apply_overwrite_fills_only_missing_regions() -> None:
    translations = {
        "欠片": Translation(jp="欠片", cn="碎片", na="Fragment"),
        "完全": Translation(jp="完全", cn="完全", tw="完全", na="Complete", kr="완전"),
    }
    overwrite = {
        "欠片": {"tw": "碎片TW", "kr": "조각"},
        # A value for a region the build already covers is never applied.
        "完全": {"kr": "WRONG"},
    }

    updated = apply_overwrite_translations(translations, overwrite)

    # Existing values win; only the missing regions are filled.
    assert translations["欠片"].tw == "碎片TW"
    assert translations["欠片"].kr == "조각"
    assert translations["完全"].kr == "완전"
    # The persisted entry holds the natively missing regions only.
    assert updated == {"欠片": {"tw": "碎片TW", "kr": "조각"}}


def test_apply_overwrite_persists_pending_and_filled_entries() -> None:
    translations = {
        # tw and kr are missing from the build; the file's na value targets a
        # region the build already covers, so it is ignored and dropped.
        "未完": Translation(jp="未完", cn="未完", na="Unfinished"),
        # Completed by the fill: the applied value persists, or the next run
        # — which rebuilds the table from Chaldea — would lose it again.
        "補完": Translation(jp="補完", cn="補完"),
        # Fully translated by the build itself: dropped as clutter.
        "完全": Translation(jp="完全", cn="完全", tw="完全", na="Complete", kr="완전"),
    }
    overwrite = {
        "未完": {"na": "Unfinished"},
        "補完": {"tw": "補完TW"},
        "完全": {"kr": "완전"},
        # Unknown to the table (e.g. pruned as unused): dropped as clutter.
        "消滅": {"na": "Gone"},
    }

    updated = apply_overwrite_translations(translations, overwrite)

    assert updated == {
        "未完": {"tw": None, "kr": None},
        "補完": {"tw": "補完TW", "na": None, "kr": None},
    }


def test_apply_overwrite_records_new_missing_entries() -> None:
    translations = {"新規": Translation(jp="新規", na="New")}

    updated = apply_overwrite_translations(translations, {})

    assert updated == {"新規": {"cn": None, "tw": None, "kr": None}}
    assert translations["新規"].kr is None  # nothing was filled


def test_overwrite_translations_to_json_sorts_keys() -> None:
    json_data = overwrite_translations_to_json({"b": {"na": "B"}, "a": {"kr": None}})

    assert list(json_data) == ["translations"]
    assert list(json_data["translations"]) == ["a", "b"]
    assert json_data["translations"]["a"] == {"kr": None}


def test_load_overwrite_translations(tmp_path) -> None:
    path = tmp_path / "overwrite_translations.json"
    assert load_overwrite_translations(path) == {}

    path.write_bytes(orjson.dumps({"translations": {"欠片": {"tw": None, "kr": "조각"}}}))

    assert load_overwrite_translations(path) == {"欠片": {"tw": None, "kr": "조각"}}


def test_load_overwrite_translations_tolerates_legacy_entries(tmp_path) -> None:
    """The pre-null format echoed jp plus the known values; the first run
    rewrites such a file in place, so it must still load."""
    path = tmp_path / "overwrite_translations.json"
    path.write_bytes(orjson.dumps({"translations": {"欠片": {"jp": "欠片", "na": "Fragment"}}}))

    assert load_overwrite_translations(path) == {"欠片": {"na": "Fragment"}}


@pytest.mark.parametrize(
    ("content", "error"),
    [
        ({"entries": {}}, "expected a {'translations': {...}} object"),
        ({"translations": {"欠片": "碎片"}}, "must be an object"),
        ({"translations": {"欠片": {"en": "Fragment"}}}, "unknown region 'en'"),
        ({"translations": {"欠片": {"na": ""}}}, "must be null or a non-empty string"),
        ({"translations": {"欠片": {"na": 3}}}, "must be null or a non-empty string"),
        ({"translations": {"欠片": {"jp": ""}}}, "jp must be a non-empty string"),
    ],
)
def test_load_overwrite_translations_rejects_malformed(tmp_path, content, error) -> None:
    path = tmp_path / "overwrite_translations.json"
    path.write_bytes(orjson.dumps(content))

    with pytest.raises(ValueError, match=re.escape(error)):
        load_overwrite_translations(path)


def test_cli_applies_and_persists_overwrite_translations(tmp_path) -> None:
    write_atlas_data(tmp_path)
    write_chaldea_data(tmp_path)
    overwrite_path = tmp_path / "overwrite_translations.json"
    overwrite_path.write_bytes(
        orjson.dumps(
            {
                "translations": {
                    # Fills the one missing region of an otherwise complete key.
                    "カリスマ B": {"kr": "카리스마"},
                    # Unknown to the table: dropped as clutter.
                    "消滅": {"na": "Gone"},
                }
            }
        )
    )
    args = [
        "--atlas-data",
        str(tmp_path / "atlas-data"),
        "--chaldea-data",
        str(tmp_path / "chaldea-data"),
        "--output-dir",
        str(tmp_path),
        "--overwrite-translations",
        str(overwrite_path),
    ]

    assert main(args) == 0

    json_data = json.loads((tmp_path / "fgo_translate.json").read_text())
    assert json_data["translations"]["カリスマ B"]["kr"] == "카리스마"

    overwrite = json.loads(overwrite_path.read_text())["translations"]
    # The fill-completed key is kept so the next run reapplies it.
    assert overwrite["カリスマ B"] == {"kr": "카리스마"}
    # Missing regions are recorded as nulls, without the known values.
    assert overwrite["マシュ・キリエライト"] == {"tw": None}
    # Stale entries are pruned.
    assert "消滅" not in overwrite

    # A second run is a no-op on the overwrite file.
    before = overwrite_path.read_bytes()
    assert main(args) == 0
    assert overwrite_path.read_bytes() == before
