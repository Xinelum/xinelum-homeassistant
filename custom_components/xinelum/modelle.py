"""Die Daten, die zwischen Xinelum und Home Assistant fliessen.

Eine eigene Schicht, weil die Rohantwort der App ein loses `dict` ist. Wer
sie ungeprueft in die Entitaeten reichen wuerde, baute genau den Fehler nach,
an dem die MQTT-Fassung gescheitert ist: dort stand am Ende die Zeichenkette
`'none'` in einem Feld, in dem HA eine Zahl erwartet, und die Entitaet
behielt still ihren alten Wert.

Hier gilt: was die App nicht als Zahl schickt, wird `None` - ein echtes
Python-`None`, kein Wort, das zufaellig so aussieht.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import Any

from .const import SENSOR_WEG, UNBEKANNT


def _text(roh: Any) -> str | None:
    """Eine nicht leere Zeichenkette oder None. Leere Felder sind kein Wert."""
    if isinstance(roh, str) and roh.strip() != "":
        return roh.strip()
    return None


def _zahl(roh: Any) -> int | float | None:
    """Eine endliche Zahl oder None.

    `bool` ist in Python eine Unterklasse von `int` und wuerde sonst als 0/1
    durchrutschen. Zeichenketten werden bewusst NICHT umgerechnet: kaeme
    jemals wieder ein `'none'` herein, soll daraus `None` werden und nicht
    ein stiller Fehler.

    Ganze Zahlen bleiben ganz. Sonst stuende in Home Assistant "4230.0"
    Sekunden, wo die MQTT-Fassung "4230" schreibt - dieselbe Zahl, zwei
    Schreibweisen, und der Verlauf haette an der Umstellung einen Knick.
    """
    if isinstance(roh, bool) or not isinstance(roh, (int, float)):
        return None
    if isinstance(roh, int):
        return roh
    if not isfinite(roh):
        return None
    return roh


def _wahrheit(roh: Any) -> bool | None:
    """True, False oder None. Alles andere ist kein Wahrheitswert."""
    return roh if isinstance(roh, bool) else None


@dataclass(frozen=True, slots=True)
class XinelumZustand:
    """Der Kinozustand, wie ihn `ZustandsExport.zustand()` nach aussen gibt."""

    kinozustand: str
    kinozustand_schluessel: str | None
    kinophase: str
    film_laeuft_roh: bool
    bildformat: str | None
    bildformat_schluessel: str | None
    spielzeit_s: int | float | None
    konfidenz_prozent: int | float | None
    bildsignal: bool | None
    quelle: str | None
    gemeldet_am: int | float | None

    @property
    def sensor_weg(self) -> bool:
        """Meldet sich gerade gar kein Sensor mehr.

        Das ist die Stelle, an der die MQTT-Fassung falsch liegt. Dort haengt
        "Film laeuft" allein an der Ausloeser-Spur, und die bleibt beim
        Wegfall des Sensors auf `filmstart` stehen, waehrend nur die Kinophase
        auf "Sensor offline" wechselt. Ergebnis: HA zeigt einen laufenden Film
        in einem Raum, in dem niemand mehr etwas misst.

        Beide Felder werden geprueft, nicht nur eines: die Kinophase fuehrt
        den Sonderwert, der Kinozustand faellt bei unbekanntem Schluessel auf
        denselben Rohwert zurueck. Welches von beiden zuerst umspringt, darf
        fuer das Ergebnis keine Rolle spielen.
        """
        return self.kinophase in SENSOR_WEG or self.kinozustand in SENSOR_WEG

    @property
    def film_laeuft(self) -> bool | None:
        """An, aus - oder ehrlich unbekannt."""
        if self.sensor_weg:
            return None
        return self.film_laeuft_roh

    @classmethod
    def aus_json(cls, roh: dict[str, Any]) -> XinelumZustand:
        """Liest die Antwort der App. Wirft nie; fehlende Felder werden None."""
        return cls(
            kinozustand=_text(roh.get("kinozustand")) or UNBEKANNT,
            kinozustand_schluessel=_text(roh.get("kinozustandSchluessel")),
            kinophase=_text(roh.get("kinophase")) or UNBEKANNT,
            film_laeuft_roh=roh.get("filmLaeuft") is True,
            bildformat=_text(roh.get("bildformat")),
            bildformat_schluessel=_text(roh.get("bildformatSchluessel")),
            spielzeit_s=_zahl(roh.get("spielzeitS")),
            konfidenz_prozent=_zahl(roh.get("konfidenzProzent")),
            bildsignal=_wahrheit(roh.get("bildsignal")),
            quelle=_text(roh.get("quelle")),
            gemeldet_am=_zahl(roh.get("gemeldetAm")),
        )


@dataclass(frozen=True, slots=True)
class XinelumAusloeser:
    """Ein gefeuerter Ausloeser, so wie ihn die Ereignis-Entitaet braucht."""

    schluessel: str
    name: str | None
    von: str | None


@dataclass(frozen=True, slots=True)
class XinelumInfo:
    """Was der Einrichtungsdialog ueber eine Instanz wissen muss."""

    freigeschaltet: bool
    # Alle Ausloeser-Schluessel des Katalogs; sie werden die `event_types`
    # der Ereignis-Entitaet. Leer, wenn der Katalog nicht lesbar war - dann
    # laeuft die Entitaet mit der eingebauten Notliste.
    ausloeser_schluessel: list[str] = field(default_factory=list)
    ausloeser_namen: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class XinelumDaten:
    """Was der Koordinator an die Entitaeten weitergibt."""

    zustand: XinelumZustand
    freigeschaltet: bool
