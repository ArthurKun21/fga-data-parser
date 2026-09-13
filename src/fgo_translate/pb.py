"""Convert the translation table into fgo_translate.pb bytes."""

from . import fgo_translate_pb2
from .pipeline import REGIONS, Translation


def translations_to_bytes(translations: dict[str, Translation]) -> bytes:
    """Serialize the flat translation table into fgo_translate.pb bytes."""
    message = fgo_translate_pb2.FgoTranslate()
    for jp_text, translation in translations.items():
        entry = message.translations[jp_text]
        entry.jp = translation.jp
        for region in REGIONS:
            name = getattr(translation, region)
            if name is not None:
                setattr(entry, region, name)
    return message.SerializeToString(deterministic=True)
