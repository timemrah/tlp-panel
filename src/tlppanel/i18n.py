"""Tiny translation helper.

Keeps the dependency list empty: no gettext catalogues to compile, just a
dictionary picked from the active locale. English is the source language.
"""

from __future__ import annotations

import locale
import os
import pathlib

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
        "Language": "Dil",
        "System default": "Sistem varsayılanı",
        "Some settings are fixed in /etc/tlp.conf and override this panel":
            "Bazı ayarlar /etc/tlp.conf dosyasında sabitlenmiş ve bu paneli geçersiz kılıyor",
        "Review": "İncele",
        "Settings fixed in /etc/tlp.conf": "/etc/tlp.conf dosyasında sabitlenmiş ayarlar",
        "TLP reads its drop-in files before /etc/tlp.conf, so these keys win over anything set here:":
            "TLP, drop-in dosyalarını /etc/tlp.conf'tan önce okur; bu yüzden şu anahtarlar "
            "buradan yapılan her ayarı geçersiz kılıyor:",
        "The panel can comment them out, leaving the lines in place with a note. Be aware that /etc/tlp.conf belongs to the tlp package: once it differs from the packaged version, upgrading tlp will ask you whether to keep your copy.":
            "Panel bu satırları yorum satırına çevirebilir; satırlar yerinde kalır, yanlarına "
            "bir not düşülür. Şunu bil: /etc/tlp.conf dosyası tlp paketine aittir. Paketteki "
            "sürümden farklılaştığı anda, tlp her güncellendiğinde sana kendi kopyanı "
            "koruyup korumayacağını soracak.",
        "Leave them alone": "Dokunma",
        "Comment them out": "Yorum satırına çevir",
        "Settings in /etc/tlp.conf commented out":
            "/etc/tlp.conf içindeki ayarlar yorum satırına çevrildi",
        "CPU speed limit": "İşlemci Hız Sınırı",
        "CPU speed limit updated": "İşlemci hız sınırı güncellendi",
        "Caps how fast the processor may run. The system mode sets it: "
        "battery saving picks the lowest step, full performance the "
        "highest, and automatic uses the lowest on battery and the "
        "highest on AC. Move the slider to override the limit for the "
        "power source in use; the next mode change resets it. A lower "
        "cap means less heat and a quieter fan, but work that takes "
        "twice as long can end up costing more energy, not less.":
            "İşlemcinin çıkabileceği en yüksek hızı sınırlar. Sistem modu bunu "
            "belirler: Tasarruf en düşük kademeyi, Performans en yükseğini "
            "seçer; Otomatik pilde en düşüğü, fişte en yükseğini kullanır. "
            "Kaydırıcıyı oynatırsan o anki güç kaynağı için sınırı elle "
            "geçersiz kılarsın; bir sonraki mod değişikliği bunu sıfırlar. "
            "Düşük sınır daha az ısı ve daha sessiz fan demek, ama iki katı "
            "süren bir iş toplamda daha az değil daha çok enerji harcayabilir.",
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


# Shown in their own language, so a speaker recognises theirs in the list.
LANGUAGE_NAMES = {"en": "English", "tr": "Türkçe"}

# The stored choice when the user wants to follow the system.
AUTO = "system"

CONFIG_FILE = (
    pathlib.Path(os.environ.get("XDG_CONFIG_HOME") or pathlib.Path.home() / ".config")
    / "tlp-panel"
    / "language"
)


def available_languages() -> list[str]:
    """Codes the app can display, the source language first."""
    return ["en"] + sorted(TRANSLATIONS)


def _detect_language() -> str:
    for env in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(env)
        if value:
            return value.split(".")[0].split("_")[0].lower()
    try:
        code, _encoding = locale.getdefaultlocale()
    except ValueError:
        code = None
    if code:
        return code.split("_")[0].lower()
    return "en"


def _read_choice() -> str:
    try:
        stored = CONFIG_FILE.read_text().strip()
    except OSError:
        return AUTO
    return stored if stored in available_languages() else AUTO


def choice() -> str:
    """The stored preference, which may be AUTO rather than a language."""
    return CHOICE


def set_language(code: str) -> None:
    """Switch the active table. Widgets built earlier keep their old text."""
    global CHOICE, LANGUAGE, _TABLE
    CHOICE = code if code in available_languages() else AUTO
    LANGUAGE = _detect_language() if CHOICE == AUTO else CHOICE
    _TABLE = TRANSLATIONS.get(LANGUAGE, {})


def save_choice(code: str) -> bool:
    """Persist the preference. A read-only home is not worth crashing over."""
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(f"{code}\n")
    except OSError:
        return False
    return True


CHOICE = AUTO
LANGUAGE = "en"
_TABLE: dict[str, str] = {}
set_language(_read_choice())


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
