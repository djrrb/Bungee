SPARSE_TTF_MASTER_TABLES = frozenset(
    ["glyf", "head", "hmtx", "loca", "maxp", "post", "vmtx"]
)
SPARSE_OTF_MASTER_TABLES = frozenset(["CFF ", "VORG", "head", "hmtx", "maxp", "vmtx"])

UFO2FT_PREFIX = "com.github.googlei18n.ufo2ft."
GLYPHS_PREFIX = "com.schriftgestaltung."

FILTERS_KEY = UFO2FT_PREFIX + "filters"

MTI_FEATURES_PREFIX = UFO2FT_PREFIX + "mtiFeatures"

FEATURE_WRITERS_KEY = UFO2FT_PREFIX + "featureWriters"

USE_PRODUCTION_NAMES = UFO2FT_PREFIX + "useProductionNames"
GLYPHS_DONT_USE_PRODUCTION_NAMES = GLYPHS_PREFIX + "Don't use Production Names"
KEEP_GLYPH_NAMES = UFO2FT_PREFIX + "keepGlyphNames"

COLOR_LAYERS_KEY = UFO2FT_PREFIX + "colorLayers"
COLOR_PALETTES_KEY = UFO2FT_PREFIX + "colorPalettes"
COLOR_LAYER_MAPPING_KEY = UFO2FT_PREFIX + "colorLayerMapping"
# sequence of [glyphs, clipBox], where 'glyphs' is in turn a sequence of
# glyph names, and 'clipBox' a 5- or 4-item sequence of numbers:
# Sequence[
#   Sequence[
#     Sequence[str, ...],  # glyph names
#     Union[
#       Sequence[float, float, float, float, float],  # variable box
#       Sequence[float, float, float, float],  # non-variable box
#     ]
#   ],
#   ...
# ]
COLR_CLIP_BOXES_KEY = UFO2FT_PREFIX + "colrClipBoxes"

OPENTYPE_CATEGORIES_KEY = "public.openTypeCategories"
OPENTYPE_META_KEY = "public.openTypeMeta"

UNICODE_VARIATION_SEQUENCES_KEY = "public.unicodeVariationSequences"

INDIC_SCRIPTS = [
    "Beng",  # Bengali
    "Cham",  # Cham
    "Deva",  # Devanagari
    "Gujr",  # Gujarati
    "Guru",  # Gurmukhi
    "Knda",  # Kannada
    "Mlym",  # Malayalam
    "Orya",  # Oriya
    "Sinh",  # Sinhala
    "Taml",  # Tamil
    "Telu",  # Telugu
]

USE_SCRIPTS = [
    # Correct as at Unicode 14.0
    "Tibt",  # Tibetan
    "Mong",  # Mongolian
    # HB has Sinhala commented out here?!
    "Buhd",  # Buhid
    "Hano",  # Hanunoo
    "Tglg",  # Tagalog
    "Tagb",  # Tagbanwa
    "Limb",  # Limbu
    "Tale",  # Tai Le
    "Bugi",  # Buginese
    "Khar",  # Kharosthi
    "Sylo",  # Syloti Nagri
    "tfng",  # Tifinagh
    "Bali",  # Balinese
    "Nko ",  # Nko
    "Phag",  # Phags Pa
    "Cham",  # Cham
    "Kali",  # Kayah Li
    "Lepc",  # Lepcha
    "Rjng",  # Rejang
    "Saur",  # Saurashtra
    "Sund",  # Sundanese
    "Egyp",  # Egyptian Hieroglyphs
    "Java",  # Javanese
    "Kthi",  # Kaithi
    "Mtei",  # Meetei Mayek
    "Lana",  # Tai Tham
    "Tavt",  # Tai Viet
    "Batk",  # Batak
    "Brah",  # Brahmi
    "Mand",  # Mandaic
    "Cakm",  # Chakma
    "Plrd",  # Miao
    "Shrd",  # Sharada
    "Takr",  # Takri
    "Dupl",  # Duployan
    "Gran",  # Grantha
    "Khoj",  # Khojki
    "Sind",  # Khudawadi
    "Mahj",  # Mahajani
    "Mani",  # Manichaean
    "Modi",  # Modi
    "Hmng",  # Pahawh Hmong
    "Phlp",  # Psalter Pahlavi
    "Sidd",  # Siddham
    "Tirh",  # Tirhuta
    "Ahom",  # Ahom
    "Mult",  # Multani
    "Adlm",  # Adlam
    "Nhks",  # Bhaiksuki
    "Marc",  # Marchen
    "Newa",  # Newa
    "Gonm",  # Masaram Gondi
    "Soyo",  # Soyombo
    "Zanb",  # Zanabazar Square
    "Dogr",  # Dogra
    "Gong",  # Gunjala Gondi
    "Rohg",  # Hanifi Rohingya
    "Maka",  # Makasar
    "Medf",  # Medefaidrin
    "Sogo",  # Old Sogdian
    "Sogd",  # Sogdian
    "Elym",  # Elymaic
    "Nand",  # Nandinagari
    "Hmnp",  # Nyiakeng Puachue Hmong
    "Wcho",  # Wancho
    "Chrs",  # Chorasmian
    "Diak",  # Dives Akuru
    "Kits",  # Khitan Small Script
    "Yezi",  # Yezidi
    "Cpmn",  # Cypro Minoan
    "Ougr",  # Old Uyghur
    "Tnsa",  # Tangsa
    "Toto",  # Toto
    "Vith",  # Vithkuqi
]
