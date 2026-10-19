"""Xinelum fuer Home Assistant.

Xinelum erkennt am Bild, was im Heimkino gerade passiert - Filmstart, Pause,
Abspann, Bildformat - und meldet es hier als Entitaeten. Die Integration
spricht direkt mit der Xinelum-App im Heimnetz, ueber den Fernstart
per Webadresse: kein MQTT-Broker, kein Server dazwischen.

Die Integration selbst ist frei. Ob die App ihre Daten herausgibt,
entscheidet der Kauf „Erweiterte Smarthome-Anbindung“ (oder ein aktives
Xinelum+) in der Xinelum-App. Fehlt er, sagt diese Integration das im
Klartext, statt einen unbekannten Fehler zu melden.
"""

from __future__ import annotations

import logging

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    XinelumAbgelehnt,
    XinelumClient,
    XinelumFehler,
    baue_basis,
)
from .const import LESEWEG_EREIGNISSE
from .coordinator import XinelumConfigEntry, XinelumKoordinator
from .push import XinelumTuerklingel

_LOGGER = logging.getLogger(__name__)

PLATTFORMEN: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.EVENT,
    Platform.SENSOR,
]


async def async_migrate_entry(hass: HomeAssistant, entry: XinelumConfigEntry) -> bool:
    """Version 1 stammt aus einer Vorabfassung mit einem anderen Weg zur App.

    Ein solcher Eintrag laesst sich nicht umschreiben, weil ihm der Schluessel der
    Webadresse fehlt: Home Assistant meldet ihn, und man richtet Xinelum
    einmal neu ein.
    """
    if entry.version == 1:
        _LOGGER.warning(
            "Dieser Xinelum-Eintrag stammt aus einer alten Fassung. "
            "Bitte entfernen und mit einer Webadresse aus der App neu einrichten"
        )
        return False
    return True


async def async_setup_entry(hass: HomeAssistant, entry: XinelumConfigEntry) -> bool:
    """Richtet Xinelum ein."""
    sitzung = async_get_clientsession(hass)
    client = XinelumClient(
        sitzung,
        baue_basis(entry.data[CONF_HOST], entry.data[CONF_PORT]),
        entry.data[CONF_TOKEN],
    )

    # Der Ausloeser-Katalog wird EINMAL beim Einrichten gelesen: er bestimmt
    # die `event_types` der Ereignis-Entitaet, und die duerfen sich zur
    # Laufzeit nicht aendern. Ist er nicht lesbar, greift die Notliste.
    try:
        _, ausloeser_namen = await client.hole_katalog()
    except XinelumAbgelehnt as fehler:
        raise ConfigEntryAuthFailed(str(fehler)) from fehler
    except XinelumFehler:
        ausloeser_namen = {}

    koordinator = XinelumKoordinator(hass, entry, client, ausloeser_namen)

    # Der erste Abruf entscheidet, ob die Einrichtung ueberhaupt traegt. Er
    # wirft bei fehlender Freischaltung, bei falschem Schluessel und bei einer
    # stummen App jeweils etwas anderes - Home Assistant zeigt danach den
    # richtigen Grund an, nicht "unbekannter Fehler".
    await koordinator.async_config_entry_first_refresh()

    entry.runtime_data = koordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATTFORMEN)

    # Erst jetzt der Strom: seine Meldungen gehen an fertige Entitaeten. Die
    # Aufgabe gehoert dem Eintrag, Home Assistant beendet sie beim Entladen.
    koordinator.starte_push(
        XinelumTuerklingel(
            sitzung=sitzung,
            url=client.adresse(LESEWEG_EREIGNISSE),
            bei_stand=koordinator.melde_stand,
            bei_ausloeser=koordinator.melde_ausloeser,
            bei_verbindungswechsel=koordinator.melde_verbindungswechsel,
        )
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: XinelumConfigEntry) -> bool:
    """Raeumt die Plattformen ab; der Strom endet mit dem Eintrag."""
    return await hass.config_entries.async_unload_platforms(entry, PLATTFORMEN)
