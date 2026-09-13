import json

import orjson

from fgo_translate import fgo_translate_pb2
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
        orjson.dumps({"カルデア学園制服": {"JP": None, "NA": "Chaldea Academy Uniform"}})
    )
    (mappings / "skill_names.json").write_bytes(
        orjson.dumps({"スキル名": {"JP": None, "NA": "Skill Name"}})
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
        ["--chaldea-data", str(tmp_path / "chaldea-data"), "--output-dir", str(tmp_path)]
    )

    assert exit_code == 0
    json_data = json.loads((tmp_path / "fgo_translate.json").read_text())
    assert list(json_data) == ["translations"]
    parsed = fgo_translate_pb2.FgoTranslate.FromString((tmp_path / "fgo_translate.pb").read_bytes())
    assert len(parsed.translations) == len(json_data["translations"])
