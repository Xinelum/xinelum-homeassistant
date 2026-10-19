"""Die Tuerklingel: der Ereignisstrom der App.

Die App reicht jede Aenderung als Server-Sent
Event weiter (`GET /xinelum/<schluessel>/ereignisse`). Zwei Arten gibt es:

    zustand    der ganze Stand, genau wie `GET .../zustand`
    ausloeser  ein gefeuerter Ausloeser, `schluessel` ist der event_type

Die Zeichen entstehen in der App an derselben Stelle wie die Antwort
auf die Abfrage. Deshalb wird der Stand hier direkt uebernommen und nicht
erst nachgefragt: es gibt nur eine Wahrheit, und sie kommt so schneller an.

Alle 25 Sekunden schickt das Tor ein Lebenszeichen (`: lebt`). Kommt
`STROM_LESEFRIST` Sekunden lang gar nichts, gilt die Leitung als tot, und
die Klingel baut sie neu auf. Solange kein Strom steht, fragt der
Koordinator alle zehn Sekunden.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterable, AsyncIterator, Callable
from typing import Any

import aiohttp
from yarl import URL

from .const import STROM_LESEFRIST, STROM_WARTEN_MAX, STROM_WARTEN_MIN

_LOGGER = logging.getLogger(__name__)

ARTEN = frozenset({"zustand", "ausloeser"})


async def lies_ereignisse(
    zeilen: AsyncIterable[bytes],
) -> AsyncIterator[tuple[str, dict[str, Any]]]:
    """Macht aus den Zeilen eines Server-Sent-Event-Stroms (Art, Daten).

    Nur bekannte Arten mit einem JSON-Objekt als Daten; alles andere wird
    still ausgesessen, ein kaputtes Ereignis bricht den Strom nicht ab.
    """
    art: str | None = None
    daten: list[str] = []
    async for roh in zeilen:
        zeile = roh.decode("utf-8", errors="replace").rstrip("\r\n")
        if zeile == "":
            if art in ARTEN and daten:
                try:
                    wert = json.loads("\n".join(daten))
                except ValueError:
                    wert = None
                if isinstance(wert, dict):
                    yield art, wert
            art, daten = None, []
            continue
        if zeile.startswith(":"):
            continue
        feld, _, inhalt = zeile.partition(":")
        inhalt = inhalt.removeprefix(" ")
        if feld == "event":
            art = inhalt
        elif feld == "data":
            daten.append(inhalt)


class XinelumTuerklingel:
    """Haelt den Ereignisstrom und meldet Stand, Ausloeser und Verbindung."""

    def __init__(
        self,
        *,
        sitzung: aiohttp.ClientSession,
        url: URL,
        bei_stand: Callable[[dict[str, Any]], None],
        bei_ausloeser: Callable[[str], None],
        bei_verbindungswechsel: Callable[[bool], None],
    ) -> None:
        self._sitzung = sitzung
        self._url = url
        self._bei_stand = bei_stand
        self._bei_ausloeser = bei_ausloeser
        self._bei_verbindungswechsel = bei_verbindungswechsel
        self._verbunden = False

    @property
    def verbunden(self) -> bool:
        """Steht der Ereignisstrom gerade."""
        return self._verbunden

    async def laufe(self) -> None:
        """Haelt den Strom, bis Home Assistant die Aufgabe beendet.

        Ein Abriss ist KEIN Fehler: die Integration fragt dann ab, und die
        Klingel versucht es wieder, erst nach einer, hoechstens nach 30
        Sekunden. Ein Kino, das ueber Nacht aus ist, ist am naechsten Abend
        von selbst wieder da.
        """
        warten = STROM_WARTEN_MIN
        while True:
            try:
                await self.runde()
                warten = STROM_WARTEN_MIN
            except asyncio.CancelledError:
                raise
            except Exception as fehler:  # noqa: BLE001 - jede Ursache endet im Abfragen
                _LOGGER.debug("Ereignisstrom von Xinelum abgerissen: %s", fehler)
            await asyncio.sleep(warten)
            warten = min(warten * 2, STROM_WARTEN_MAX)

    async def runde(self) -> None:
        """Eine Verbindung, vom Aufbau bis zum Ende des Stroms."""
        zeitgrenze = aiohttp.ClientTimeout(
            total=None, sock_connect=10, sock_read=STROM_LESEFRIST
        )
        async with self._sitzung.get(
            self._url, headers={"Accept": "text/event-stream"}, timeout=zeitgrenze
        ) as antwort:
            if antwort.status != 200:  # noqa: PLR2004
                raise ConnectionError(
                    f"Ereignisstrom antwortet mit HTTP {antwort.status}"
                )
            self._setze_verbunden(True)
            try:
                async for art, daten in lies_ereignisse(antwort.content):
                    self._verteile(art, daten)
            finally:
                self._setze_verbunden(False)

    def _setze_verbunden(self, verbunden: bool) -> None:
        if verbunden == self._verbunden:
            return
        self._verbunden = verbunden
        self._bei_verbindungswechsel(verbunden)

    def _verteile(self, art: str, daten: dict[str, Any]) -> None:
        """Ein Ereignis an den Koordinator. Eine Klingel sprengt nie die Tuer."""
        try:
            if art == "zustand":
                self._bei_stand(daten)
            elif art == "ausloeser":
                schluessel = daten.get("schluessel")
                if isinstance(schluessel, str) and schluessel != "":
                    self._bei_ausloeser(schluessel)
        except Exception:
            _LOGGER.exception("Ein Ereignis von Xinelum liess sich nicht verarbeiten")
