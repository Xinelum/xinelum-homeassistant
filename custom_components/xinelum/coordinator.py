"""Der Koordinator: eine Wahrheit, zwei Wege sie zu erfahren.

Push, wenn moeglich - abfragen, wenn noetig. Die Entitaeten merken davon
nichts, sie lesen immer denselben `XinelumDaten`-Satz.

Verfuegbarkeit ist hier die halbe Miete. Die MQTT-Fassung loest das ueber das
Last Will des Brokers: reisst die Verbindung, schreibt der Broker "offline",
und Home Assistant zeigt "nicht verfuegbar" statt eines eingefrorenen Wertes.
Ohne Broker gibt es kein Last Will, also muss die Integration es selbst
koennen. Sie tut es an drei Stellen:

  1. Die App antwortet nicht (oder fuehrt gerade nicht) -> UpdateFailed -> unavailable
  2. Das Tor nimmt den Schluessel nicht -> ConfigEntryAuthFailed -> Reparaturfluss
  3. Die Freischaltung faellt weg       -> UpdateFailed + Reparatur-Hinweis

Fall 3 ist der wichtigste: Erstattung, Kontowechsel, beendetes Xinelum+,
und ploetzlich liefert die App nichts mehr. Dann sollen die Entitaeten
NICHT auf dem letzten Wert stehenbleiben, und der Grund soll dastehen.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    XinelumAbgelehnt,
    XinelumClient,
    XinelumFehler,
    XinelumNichtErreichbar,
    deute_stand,
)
from .const import (
    DOMAIN,
    ISSUE_NICHT_FREIGESCHALTET,
    POLL_INTERVALL,
    PUSH_INTERVALL,
)
from .modelle import XinelumDaten
from .push import XinelumTuerklingel

_LOGGER = logging.getLogger(__name__)

type XinelumConfigEntry = ConfigEntry[XinelumKoordinator]

# Nach einem Push wird sofort nachgefasst, mehrere Ereignisse dicht
# hintereinander aber zu einer Anfrage zusammengezogen. Der Vorgabewert von
# Home Assistant (10 s) waere hier falsch: eine Kinophase, die zehn Sekunden
# zu spaet ankommt, hat das Licht schon verpasst.
ANFRAGE_ABKUEHLUNG = 0.5


class XinelumKoordinator(DataUpdateCoordinator[XinelumDaten]):
    """Holt den Kinozustand und haelt die Push-Verbindung."""

    config_entry: XinelumConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: XinelumConfigEntry,
        client: XinelumClient,
        ausloeser_namen: dict[str, str],
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=POLL_INTERVALL,
            request_refresh_debouncer=Debouncer(
                hass,
                _LOGGER,
                cooldown=ANFRAGE_ABKUEHLUNG,
                immediate=True,
            ),
        )
        self.client = client
        self.ausloeser_namen = ausloeser_namen
        self._ausloeser_hoerer: list[Callable[[str], None]] = []
        self._tuerklingel: XinelumTuerklingel | None = None
        self._freischaltung_gemeldet = False

    @property
    def push_steht(self) -> bool:
        """Sagt, ob gerade wirklich gepusht wird statt abgefragt."""
        return self._tuerklingel is not None and self._tuerklingel.verbunden

    # ---------------------------------------------------------------- Push

    @callback
    def starte_push(self, tuerklingel: XinelumTuerklingel) -> None:
        """Haengt die Tuerklingel ein, als Hintergrundaufgabe des Eintrags.

        Home Assistant beendet sie selbst, wenn der Eintrag entladen wird.
        """
        self._tuerklingel = tuerklingel
        self.config_entry.async_create_background_task(
            self.hass, tuerklingel.laufe(), name="xinelum_ereignisstrom"
        )

    @callback
    def melde_stand(self, roh: dict[str, Any]) -> None:
        """Ein Stand aus dem Ereignisstrom: derselbe wie auf Abfrage."""
        try:
            zustand, freigeschaltet = deute_stand(roh)
        except XinelumFehler as fehler:
            _LOGGER.debug("Unlesbarer Stand im Ereignisstrom: %s", fehler)
            return
        if not freigeschaltet or zustand is None:
            self._melde_fehlende_freischaltung()
            self.async_set_update_error(
                UpdateFailed(
                    "Diese Xinelum-App hat die Anbindung nicht mehr freigeschaltet"
                )
            )
            return
        self._raeume_freischaltungs_hinweis_weg()
        self.async_set_updated_data(XinelumDaten(zustand=zustand, freigeschaltet=True))

    @callback
    def _setze_intervall(self, push_steht: bool) -> None:
        """Push heisst nicht: gar nicht mehr fragen.

        Ein Sicherheitsnetz bleibt. Ein Ereignisstrom kann aus Sicht des
        Clients stehen und trotzdem tot sein (halboffene TCP-Verbindung hinter
        einem Router, der still aufraeumt). Alle fuenf Minuten nachzufassen
        kostet nichts und deckt genau diesen Fall auf.
        """
        neu = PUSH_INTERVALL if push_steht else POLL_INTERVALL
        if self.update_interval != neu:
            self.update_interval = neu
            self._schedule_refresh()

    @callback
    def melde_verbindungswechsel(self, verbunden: bool) -> None:
        """Die Tuerklingel hat sich verbunden oder getrennt."""
        self._setze_intervall(verbunden)

    # ------------------------------------------------------------ Ausloeser

    @callback
    def hoere_ausloeser(self, hoerer: Callable[[str], None]) -> Callable[[], None]:
        """Meldet einen Hoerer fuer gefeuerte Ausloeser an."""
        self._ausloeser_hoerer.append(hoerer)

        @callback
        def abmelden() -> None:
            self._ausloeser_hoerer.remove(hoerer)

        return abmelden

    @callback
    def melde_ausloeser(self, schluessel: str) -> None:
        """Reicht einen gefeuerten Ausloeser an die Ereignis-Entitaet weiter."""
        for hoerer in list(self._ausloeser_hoerer):
            hoerer(schluessel)

    # --------------------------------------------------------------- Daten

    async def _async_update_data(self) -> XinelumDaten:
        try:
            zustand, freigeschaltet = await self.client.hole_status()
        except XinelumAbgelehnt as fehler:
            # Kein UpdateFailed: eine falsche Kennung heilt nicht von selbst.
            # Home Assistant soll den Nutzer fragen, nicht ewig weiterversuchen.
            raise ConfigEntryAuthFailed(str(fehler)) from fehler
        except XinelumNichtErreichbar as fehler:
            raise UpdateFailed(str(fehler)) from fehler
        except XinelumFehler as fehler:
            raise UpdateFailed(str(fehler)) from fehler

        if not freigeschaltet or zustand is None:
            self._melde_fehlende_freischaltung()
            # UpdateFailed statt stiller Weiterlauf: die Entitaeten werden
            # "nicht verfuegbar" und behalten NICHT ihren letzten Wert.
            raise UpdateFailed(
                "Diese Xinelum-App hat die Anbindung nicht mehr freigeschaltet"
            )

        self._raeume_freischaltungs_hinweis_weg()
        return XinelumDaten(zustand=zustand, freigeschaltet=True)

    @callback
    def _melde_fehlende_freischaltung(self) -> None:
        if self._freischaltung_gemeldet:
            return
        self._freischaltung_gemeldet = True
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            f"{ISSUE_NICHT_FREIGESCHALTET}_{self.config_entry.entry_id}",
            is_fixable=False,
            is_persistent=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=ISSUE_NICHT_FREIGESCHALTET,
            translation_placeholders={"adresse": str(self.client.basis)},
        )

    @callback
    def _raeume_freischaltungs_hinweis_weg(self) -> None:
        if not self._freischaltung_gemeldet:
            return
        self._freischaltung_gemeldet = False
        ir.async_delete_issue(
            self.hass,
            DOMAIN,
            f"{ISSUE_NICHT_FREIGESCHALTET}_{self.config_entry.entry_id}",
        )
