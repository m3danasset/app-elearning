"""Bahasa tampilan: layar MURID (termasuk trial) memakai English, layar login, guru, dan
admin tetap Bahasa Indonesia.

Bahasa diatur saat login (window.py: set_role). Komponen yang dipakai bersama semua peran
(sidebar, search palette, dialog konfirmasi, file browser) memanggil L("teks Indonesia",
"English text") sehingga mengikuti bahasa yang sedang aktif. Layar khusus murid boleh
langsung memakai teks English.
"""

_lang = {"code": "id"}


def set_lang(code):
    _lang["code"] = "en" if code == "en" else "id"


def set_role(role):
    """role: "student" / "trial" -> English, lainnya -> Indonesia."""
    set_lang("en" if role in ("student", "trial") else "id")


def is_en():
    return _lang["code"] == "en"


def L(id_text, en_text):
    """Teks sesuai bahasa aktif."""
    return en_text if _lang["code"] == "en" else id_text
