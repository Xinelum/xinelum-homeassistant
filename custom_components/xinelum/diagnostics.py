"""Diagnosedaten fuer eine Fehlersuche.

Ein Bildproblem in Xinelum wird zuerst an der Diagnose-Box gelesen und nicht
am Quelltext; dieselbe Haltung gilt hier. Was fehlt, soll dastehen.

Der Schluessel der Webadresse wird NIE ausgegeben: mit ihm laesst sich das
Kino starten.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.core import HomeAssistant

from .coordinator import XinelumConfigEntry

ZU_SCHWAERZEN = {CONF_TOKEN}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: XinelumConfigEntry
) -> dict[str, Any]:
    """Alles, was bei einer Fehlersuche hilft."""
    koordinator = entry.runtime_data
    daten = koordinator.data
    return {
        "einrichtung": async_redact_data(
            {
                CONF_HOST: entry.data.get(CONF_HOST),
                CONF_PORT: entry.data.get(CONF_PORT),
                CONF_TOKEN: entry.data.get(CONF_TOKEN),
            },
            ZU_SCHWAERZEN,
        ),
        "verbindung": {
            "adresse": str(koordinator.client.basis),
            "push_steht": koordinator.push_steht,
            "abfrage_intervall_s": (
                koordinator.update_interval.total_seconds()
                if koordinator.update_interval
                else None
            ),
            "letzter_abruf_erfolgreich": koordinator.last_update_success,
        },
        "zustand": (
            {
                **asdict(daten.zustand),
                # Die beiden Ableitungen mitschreiben: an genau ihnen ist die
                # MQTT-Fassung gescheitert, sie gehoeren in jede Fehlersuche.
                "abgeleitet_sensor_weg": daten.zustand.sensor_weg,
                "abgeleitet_film_laeuft": daten.zustand.film_laeuft,
            }
            if daten is not None
            else None
        ),
        "ausloeser_katalog": sorted(koordinator.ausloeser_namen),
    }
