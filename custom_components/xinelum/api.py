"""Der HTTP-Zugang zur Xinelum-App.

Diese Datei kennt genau diese Ausgaenge, und der Unterschied zwischen ihnen
ist der eigentliche Wert dieser Integration:

    XinelumNichtErreichbar     Adresse falsch, App aus, Netz weg
    XinelumAbgelehnt           erreichbar, aber der Schluessel passt nicht
    XinelumRuht                die App laeuft, fuehrt das Kino aber gerade
                               nicht auf diesem Geraet
    XinelumNichtFreigeschaltet erreichbar, Schluessel stimmt, der Kauf fehlt
    XinelumAntwortUnbrauchbar  da antwortet etwas, aber es ist kein Xinelum
    (kein Fehler)              erreichbar, Schluessel stimmt, freigeschaltet

Der Fall „Kauf fehlt“ wird beim ersten Start der haeufigste sein: jemand
laedt die kostenlose Integration, traegt seine Adresse ein und hat die
„Erweiterte Smarthome-Anbindung“ (oder Xinelum+) noch nicht. Das ist KEIN
Absturz und kein "unbekannter Fehler", sondern eine klare Auskunft.

ANMELDUNG: der Schluessel des Fernstarts per Webadresse steht im Pfad, wie
bei den Webadressen selbst. Ohne passenden Schluessel
antwortet das Tor immer gleich: 404 mit seinem Satz.
"""

from __future__ import annotations

import logging
from http import HTTPStatus
from typing import Any

import aiohttp
from yarl import URL

from .const import (
    BEREICH_HOMEASSISTANT,
    LESEWEG_KATALOG,
    LESEWEG_ZUSTAND,
    PFAD_PRAEFIX,
    STAND_VERSION,
)
from .modelle import XinelumInfo, XinelumZustand

_LOGGER = logging.getLogger(__name__)

# Die App antwortet im Heimnetz in Millisekunden. Zehn Sekunden sind
# grosszuegig und trotzdem kurz genug, dass der Einrichtungsdialog nicht
# minutenlang haengt.
ZEITGRENZE = aiohttp.ClientTimeout(total=10)


class XinelumFehler(Exception):
    """Oberklasse aller Fehler dieser Integration."""


class XinelumNichtErreichbar(XinelumFehler):
    """Unter der Adresse antwortet nichts."""


class XinelumAbgelehnt(XinelumFehler):
    """Das Tor antwortet, der Schluessel passt aber nicht (404 mit Satz)."""


class XinelumRuht(XinelumFehler):
    """Die App antwortet, fuehrt das Kino aber gerade nicht auf diesem Geraet."""


class XinelumNichtFreigeschaltet(XinelumFehler):
    """Die App antwortet, aber die Anbindung ist nicht gekauft."""


class XinelumAntwortUnbrauchbar(XinelumFehler):
    """Es antwortet etwas, aber es ist kein Xinelum."""


def baue_basis(host: str, port: int) -> URL:
    """Baut die Basisadresse. Getrennt, damit der Dialog sie anzeigen kann."""
    return URL.build(scheme="http", host=host, port=port)


def deute_stand(roh: Any) -> tuple[XinelumZustand | None, bool]:
    """Liest einen Stand der App (HTTP oder Ereignisstrom), streng.

    Antwort: Zustand und Freischaltung. Ohne Freischaltung gibt es keinen
    Zustand. Wirft `XinelumAntwortUnbrauchbar`, wenn es kein Stand ist.
    """
    if not isinstance(roh, dict) or roh.get("version") != STAND_VERSION:
        raise XinelumAntwortUnbrauchbar("Die Antwort ist kein Stand von Xinelum")
    freischaltungen = roh.get("freischaltungen")
    freigeschaltet = (
        isinstance(freischaltungen, dict)
        and freischaltungen.get(BEREICH_HOMEASSISTANT) is True
    )
    if not freigeschaltet:
        return None, False
    zustand = roh.get("zustand")
    if not isinstance(zustand, dict):
        raise XinelumAntwortUnbrauchbar("Die Antwort enthaelt keinen Kinozustand")
    return XinelumZustand.aus_json(zustand), True


class XinelumClient:
    """Liest den Kinozustand. Schreibt nie."""

    def __init__(
        self,
        sitzung: aiohttp.ClientSession,
        basis: URL,
        token: str,
    ) -> None:
        self._sitzung = sitzung
        self._basis = basis
        self._token = token

    @property
    def basis(self) -> URL:
        """Die Adresse, unter der Xinelum antwortet (ohne Schluessel)."""
        return self._basis

    def adresse(self, weg: str) -> URL:
        """Die volle Adresse eines Lesewegs, mit Schluessel im Pfad."""
        return self._basis.with_path(f"/{PFAD_PRAEFIX}/{self._token}/{weg}")

    async def _hole(self, weg: str) -> dict[str, Any]:
        """Holt eine JSON-Antwort und uebersetzt jeden Fehlschlag in einen Grund."""
        adresse = self.adresse(weg)
        # In Meldungen nie der Schluessel: nur Basis und Weg.
        ziel = f"{self._basis}/…/{weg}"
        try:
            antwort = await self._sitzung.get(adresse, timeout=ZEITGRENZE)
        except TimeoutError as fehler:
            raise XinelumNichtErreichbar(
                f"{ziel} antwortet nicht innerhalb der Zeitgrenze"
            ) from fehler
        except aiohttp.ClientError as fehler:
            raise XinelumNichtErreichbar(f"{ziel} ist nicht erreichbar") from fehler

        async with antwort:
            try:
                # Die App schickt application/json; ein fremder Dienst schickt
                # HTML. content_type=None laesst uns das selbst merken.
                inhalt: Any = await antwort.json(content_type=None)
            except (aiohttp.ClientError, ValueError):
                inhalt = None
            hat_satz = isinstance(inhalt, dict) and isinstance(inhalt.get("satz"), str)
            if antwort.status == HTTPStatus.NOT_FOUND and hat_satz:
                # Das Tor antwortet ohne passenden Schluessel immer so.
                raise XinelumAbgelehnt("Xinelum nimmt diesen Schluessel nicht an")
            if antwort.status == HTTPStatus.SERVICE_UNAVAILABLE and hat_satz:
                raise XinelumRuht(
                    "Xinelum fuehrt das Kino gerade nicht auf diesem Geraet"
                )
            if antwort.status != HTTPStatus.OK:
                raise XinelumAntwortUnbrauchbar(
                    f"{ziel} antwortet mit HTTP {antwort.status}"
                )
        if not isinstance(inhalt, dict):
            raise XinelumAntwortUnbrauchbar(f"{ziel} antwortet nicht mit einem Objekt")
        return inhalt

    async def hole_status(self) -> tuple[XinelumZustand | None, bool]:
        """Liefert Kinozustand und Freischaltung.

        Bewusst OHNE hier schon zu werfen, wenn die Freischaltung fehlt: der
        Aufrufer entscheidet, ob das ein Abbruch (Einrichtung) oder ein Grund
        fuer "nicht verfuegbar" (laufender Betrieb) ist.
        """
        return deute_stand(await self._hole(LESEWEG_ZUSTAND))

    async def hole_katalog(self) -> tuple[list[str], dict[str, str]]:
        """Die Ausloeser-Schluessel und ihre Klartextnamen.

        Sie werden die `event_types` der Ereignis-Entitaet. Faellt der Katalog
        aus, ist das kein Grund, die Einrichtung abzubrechen - die Entitaet
        laeuft dann mit ihrer eingebauten Notliste.
        """
        try:
            roh = await self._hole(LESEWEG_KATALOG)
        except XinelumFehler as fehler:
            _LOGGER.debug("Ausloeser-Katalog nicht lesbar: %s", fehler)
            return [], {}

        eintraege = roh.get("katalog")
        if not isinstance(eintraege, list):
            return [], {}

        schluessel: list[str] = []
        namen: dict[str, str] = {}
        for eintrag in eintraege:
            if not isinstance(eintrag, dict):
                continue
            key = eintrag.get("schluessel")
            if not isinstance(key, str) or key == "" or key in namen:
                continue
            schluessel.append(key)
            name = eintrag.get("name")
            namen[key] = name if isinstance(name, str) and name != "" else key
        return schluessel, namen

    async def pruefe_einrichtung(self) -> XinelumInfo:
        """Der Handschlag des Einrichtungsdialogs.

        Wirft `XinelumNichtFreigeschaltet`, wenn die App erreichbar ist und
        der Schluessel stimmt, die Anbindung aber nicht gekauft ist. Das ist
        ein eigener Fehler und ausdruecklich kein Sammelbegriff.
        """
        _, freigeschaltet = await self.hole_status()
        if not freigeschaltet:
            raise XinelumNichtFreigeschaltet(
                "Diese Xinelum-App hat die Anbindung nicht freigeschaltet"
            )
        schluessel, namen = await self.hole_katalog()
        return XinelumInfo(
            freigeschaltet=True,
            ausloeser_schluessel=schluessel,
            ausloeser_namen=namen,
        )
