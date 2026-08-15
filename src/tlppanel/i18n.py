"""Tiny translation helper.

Keeps the dependency list empty: no gettext catalogues to compile, just a
dictionary picked from the active locale. English is the source language.
"""

from __future__ import annotations

import locale
import os

TRANSLATIONS: dict[str, dict[str, str]] = {
    "tr": {
        "TLP Panel": "TLP Paneli",
        "Power draw": "Anlık çekim",
        "Charge power": "Şarj gücü",
        "Idle on AC": "Fişte, pil kullanılmıyor",
        "On AC power": "Fişte",
        "On battery": "Pilde",
        "Battery": "Pil",
        "System mode": "Sistem Modu",
        "Health": "Sağlık",
        "Cycles": "Şarj Döngüsü",
        "Charge limit": "Şarj Sınırı",
        "Charge limit set to": "Şarj sınırı ayarlandı:",
        "Lithium batteries age faster when kept near a full charge. "
        "Stopping at 80% trades some runtime for a longer service life. "
        "The slider writes the limit to the battery firmware, so it "
        "survives reboots.":
            "Lityum piller tam şarja yakın tutulduğunda daha hızlı yaşlanır. "
            "%80'de durdurmak bir miktar çalışma süresinden feragat edip pil "
            "ömrünü uzatır. Kaydırıcı sınırı pil firmware'ine yazar, yeniden "
            "başlatmalarda kalıcıdır.",
        "Charging": "Şarj oluyor",
        "Discharging": "Boşalıyor",
        "Full": "Dolu",
        "Not charging": "Şarj olmuyor",
        "Unknown": "Bilinmiyor",
        "Estimated runtime": "Tahmini Kullanım Süresi",
        "Estimated charging time": "Tahmini Şarj Süresi",
        "Right now": "Anlık Enerjiye Göre",
        "At the charge limit": "Sınırlandırılmış Şarj",
        "At 100%": "Tam Şarj",
        "Main menu": "Ana menü",
        "Automatic": "Otomatik",
        "Battery saving": "Tasarruf",
        "Full performance": "Performans",
        "Charge to 100% once": "Bir kereliğine %100 şarj et",
        "Wi-Fi power saving": "Wi-Fi Güç Tasarrufu",
        "Adaptive backlight": "Adaptif Arka Işık",
        "Not supported by this display": "Bu ekranda desteklenmiyor — sürücü ayarı kabul ediyor ama uygulamıyor",
        "Sleep idle devices": "Boştaki Donanımı Uyut",
        "Idle device sleep updated": "Donanım uyku ayarı güncellendi",
        "Lets idle PCI devices — the card reader, the sound chip, "
        "controllers — power down between uses. Automatic keeps them "
        "awake on AC and lets them sleep on battery. Individual "
        "devices can be exempted in the TLP configuration; the panel "
        "leaves those exemptions untouched.":
            "Boştaki PCI cihazlarının — kart okuyucu, ses yongası, "
            "denetleyiciler — kullanılmadıkları sürece uykuya geçmesini "
            "sağlar. Otomatik, fişteyken uyanık tutar, pilde uyumalarına "
            "izin verir. Tek tek cihazlar TLP yapılandırmasında muaf "
            "tutulabilir; panel bu muafiyetlere dokunmaz.",
        "Off": "Kapalı",
        "On": "Açık",
        "Adaptive backlight updated": "Adaptif arka ışık güncellendi",
        "Wi-Fi power saving updated": "Wi-Fi güç tasarrufu güncellendi",
        "The panel dims and shifts contrast to save power. Higher "
        "levels save more but wash out colours. 0 turns it off. "
        "Most people leave it off on AC and low on battery.":
            "Ekran, güç tasarrufu için parlaklığı ve kontrastı içeriğe göre "
            "kısar. Yüksek seviye daha çok tasarruf eder ama renkleri "
            "soluklaştırır. 0 kapatır. Çoğu kişi fişteyken kapalı, pilde "
            "düşük seviyede bırakır.",
        "Automatic keeps the radio awake on AC and lets it sleep on "
        "battery, which is TLP's default. Saving costs a little "
        "latency, and a few chipsets drop the connection when it is "
        "enabled — turn it off if your Wi-Fi becomes unreliable.":
            "Otomatik, fişteyken kartı uyanık tutar, pilde uyumasına izin "
            "verir; TLP'nin varsayılanı budur. Tasarruf bir miktar gecikme "
            "getirir ve bazı kartlar açıkken bağlantıyı düşürür — Wi-Fi'ın "
            "kararsızlaşırsa kapat.",
        "off": "kapalı",
        "on": "açık",
        "TLP is not installed": "TLP kurulu değil",
        "Install it with: sudo apt install tlp": "Kurmak için: sudo apt install tlp",
        "TLP is installed but disabled": "TLP kurulu ama devre dışı",
        "No battery found": "Pil bulunamadı",
        "Refresh": "Yenile",
        "About": "Hakkında",
        "Project page": "Proje sayfası",
        "Report an issue": "Sorun bildir",
        "Licence: GPL-3.0-or-later": "Lisans: GPL-3.0 veya sonrası",
        "Authentication failed or was cancelled": "Yetkilendirme başarısız ya da iptal edildi",
        "Mode switched to automatic": "Otomatik moda geçildi",
        "Battery saving applied": "Tasarruf modu uygulandı",
        "Full performance applied": "Performans modu uygulandı",
        "Charging to 100% this time": "Bu seferlik %100'e kadar şarj edilecek",
        "Reading power state failed": "Güç durumu okunamadı",
        "hours_short": "sa",
        "minutes_short": "dk",
    }
}


def _detect_language() -> str:
    for env in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(env)
        if value:
            return value.split(".")[0].split("_")[0].lower()
    try:
        code, _ = locale.getdefaultlocale()
    except ValueError:
        code = None
    if code:
        return code.split("_")[0].lower()
    return "en"


LANGUAGE = _detect_language()
_TABLE = TRANSLATIONS.get(LANGUAGE, {})


def _(text: str) -> str:
    """Translate a source string, falling back to English."""
    return _TABLE.get(text, text)


def N_(text: str) -> str:
    """Mark a string for translation without translating it yet.

    Used for literals that are stored first and translated later, such as
    table values or messages passed to a helper. Tools that collect
    translatable strings look for this the same way they look for `_`.
    """
    return text


def format_duration(hours: float | None) -> str | None:
    """Human readable duration, e.g. '5 h 30 min'."""
    if hours is None or hours <= 0:
        return None
    total_minutes = int(round(hours * 60))
    h, m = divmod(total_minutes, 60)
    unit_h = _("hours_short") if LANGUAGE in TRANSLATIONS else "h"
    unit_m = _("minutes_short") if LANGUAGE in TRANSLATIONS else "min"
    if unit_h == "hours_short":
        unit_h = "h"
    if unit_m == "minutes_short":
        unit_m = "min"
    if h and m:
        return f"{h} {unit_h} {m} {unit_m}"
    if h:
        return f"{h} {unit_h}"
    return f"{m} {unit_m}"
