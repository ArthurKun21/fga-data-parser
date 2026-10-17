import json

import orjson

from fgo_translate import fgo_translate_pb2
from fgo_translate.atlas import build_atlas_entries
from fgo_translate.cli import main
from fgo_translate.pb import translations_to_bytes
from fgo_translate.pipeline import (
    Translation,
    build_translations,
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
    for empty_table in ("td_names", "td_detail", "buff_names", "buff_detail"):
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
                nps=[{"id": 11, "num": 1, "name": "約束された勝利の剣"}],
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
        ],
        ".na": [
            servant(
                # The official NA text keeps "Altria"; values are never renamed.
                name="Altria Pendragon",
                skills=na_skills,
                nps=[{"id": 11, "num": 1, "name": "Excalibur"}],
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
        ],
        # CN only translates the servant name so far.
        ".cn": [servant(name="阿尔托莉雅·潘德拉贡", skills=[], nps=[], append_passives=[])],
        ".tw": [
            servant(
                # The fullwidth stop is the official TW text, not a typo.
                name="阿爾托莉亞．潘德拉剛",  # noqa: RUF001
                skills=tw_skills,
                nps=[{"id": 888, "num": 1, "name": "勝利の剣TW"}],
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
    assert entries["対魔力 C"] == {"na": "Magic Resistance C"}
    assert entries["対魔力"] == {"na": "Magic Resistance"}
    assert entries["自身の弱体耐性をアップ[{0}]"] == {"na": "Increase debuff resistance [{0}]"}

    assert entries["魔術礼装･カルデア"] == {"na": "Chaldea Combat Uniform"}
    assert entries["応急手当"] == {"na": "First Aid"}
    assert entries["星の王冠"] == {"na": "Crown of the Star"}
    assert entries["旧星の王冠"] == {"na": "Old Star Crown"}
    assert entries["王冠の輝き"] == {"na": "Radiant Crown"}
    assert all("kr" not in regions for regions in entries.values())


def test_build_atlas_entries_without_jp_data(tmp_path) -> None:
    assert build_atlas_entries(tmp_path / "missing") == {}


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
