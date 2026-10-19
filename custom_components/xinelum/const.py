"""Feste Werte der Xinelum-Integration.

Alles, was an mehr als einer Stelle gebraucht wird, steht hier. Insbesondere
die beiden Sonderwerte der App, an denen die Integration erkennt, dass der
Sensor gerade gar nichts weiss.

DER WEG ZUR APP (seit 19.10.2026): Home Assistant liest direkt bei der
Xinelum-App, ueber den Fernstart per Webadresse und mit dessen Schluessel.
Nur das Geraet, das das Kino gerade fuehrt, antwortet.

    GET http://<geraet>:47474/xinelum/<schluessel>/zustand
    GET http://<geraet>:47474/xinelum/<schluessel>/katalog
    GET http://<geraet>:47474/xinelum/<schluessel>/ereignisse   (Server-Sent Events)
"""

from __future__ import annotations

import hashlib
import re
from datetime import timedelta
from typing import Final
from urllib.parse import urlsplit

DOMAIN: Final = "xinelum"

# Das eine Eingabefeld des Dialogs: eine Webadresse aus der App
# (oder, wenn Xinelum gefunden wurde, nur ihr Schluessel).
CONF_ADRESSE: Final = "adresse"

# Der Port, auf dem die App die Webadressen annimmt.
STANDARD_PORT: Final = 47474
PFAD_PRAEFIX: Final = "xinelum"
LESEWEG_ZUSTAND: Final = "zustand"
LESEWEG_KATALOG: Final = "katalog"
LESEWEG_EREIGNISSE: Final = "ereignisse"

# Die Version des Standes, die diese Integration liest.
STAND_VERSION: Final = 1

# Unter diesem Bonjour-Typ meldet sich die App im Heimnetz.
DIENST_TYP: Final = "_xinelum-ha._tcp"

# Der Bereich, den die „Erweiterte Smarthome-Anbindung“ oder ein aktives
# Xinelum+ freischaltet. So heisst er in der Antwort der App.
BEREICH_HOMEASSISTANT: Final = "homeassistant"
# Wie der Kauf in der App heisst (seit 18.10.2026). Steht in jeder Meldung,
# die einen fehlenden Kauf erklaert.
KAUF_NAME: Final = "Erweiterte Smarthome-Anbindung"

# Rueckfall, solange kein Push steht. Bewusst kurz: eine Kinophase, die
# 30 Sekunden zu spaet ankommt, ist fuer eine Lichtsteuerung wertlos.
POLL_INTERVALL: Final = timedelta(seconds=10)
# Wenn Push steht, wird nur noch als Sicherheitsnetz nachgefasst.
PUSH_INTERVALL: Final = timedelta(minutes=5)
# Das Tor schickt alle 25 Sekunden ein Lebenszeichen. Kommt so lange nichts,
# ist die Leitung tot, auch wenn TCP es noch nicht gemerkt hat.
STROM_LESEFRIST: Final = 70
# Neuer Versuch nach einem Abriss: erst nach einer, hoechstens nach 30 Sekunden.
STROM_WARTEN_MIN: Final = 1
STROM_WARTEN_MAX: Final = 30

# Sonderwerte der App. Steht einer davon in der Kinophase
# oder im Kinozustand, weiss Xinelum nichts - dann darf "Film laeuft" NICHT
# false und erst recht nicht der alte Wert sein, sondern unbekannt.
SENSOR_OFFLINE: Final = "Sensor offline"
UNBEKANNT: Final = "unbekannt"
SENSOR_WEG: Final = frozenset({SENSOR_OFFLINE, UNBEKANNT})

# Repair-Kennung fuer die weggefallene Freischaltung.
ISSUE_NICHT_FREIGESCHALTET: Final = "nicht_freigeschaltet"

# Notliste der Ausloeser-Schluessel, falls der Katalog der App beim
# Einrichten nicht lesbar war. Sie muss zum Katalog der App passen; ein
# zusaetzlicher Schluessel dort taucht nach dem naechsten Neuladen der
# Integration von selbst auf, weil dann der echte Katalog gilt.
# Ohne "sensor-offline": dieser Ausloeser ist seit dem 17.10.2026 nur noch
# intern und kommt im Katalog der App nicht mehr vor.
AUSLOESER_NOTLISTE: Final = (
    "menue",
    "filmstart",
    "pause",
    "abspann-1",
    "abspann-2",
    "post-credit",
    "filmende",
    "dunkel",
    "aufwachen",
    "kein-bild",
    "format-4-3",
    "format-16-9",
    "format-1-85",
    "format-2-0",
    "format-21-9",
)

_SCHLUESSEL = re.compile(r"^[0-9a-f]{64}$")


def instanzkennung(token: str) -> str:
    """Eine Kennung des Haushalts: dieselbe fuer denselben Schluessel.

    Dieselbe Rechnung wie `Triggerpfad.instanzkennung` im Tor, das sie im
    Bonjour-TXT als `id` wirbt. Aus ihr laesst sich der Schluessel nicht
    gewinnen.
    """
    return hashlib.sha256(f"xinelum-ha:{token}".encode()).hexdigest()[:12]


def lies_adresse(eingabe: str) -> tuple[str | None, int | None, str] | None:
    """Liest eine Webadresse aus der App oder einen blanken Schluessel.

    Antwort: (Host, Port, Schluessel); Host und Port sind None beim blanken
    Schluessel. None, wenn die Eingabe weder das eine noch das andere ist.
    """
    text = eingabe.strip()
    if _SCHLUESSEL.match(text.lower()):
        return None, None, text.lower()
    try:
        teile = urlsplit(text)
        port = teile.port
    except ValueError:
        return None
    if teile.scheme != "http" or not teile.hostname:
        return None
    stuecke = [s for s in teile.path.split("/") if s]
    if len(stuecke) < 2 or stuecke[0] != PFAD_PRAEFIX:  # noqa: PLR2004
        return None
    schluessel = stuecke[1].lower()
    if not _SCHLUESSEL.match(schluessel):
        return None
    return teile.hostname, port or STANDARD_PORT, schluessel
