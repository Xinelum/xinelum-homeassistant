"""Die Ausloeser als Ereignis-Entitaet.

Ein Filmstart ist ein Moment, kein Zustand. Eine `event`-Entitaet ist dafuer
das richtige Werkzeug: Home Assistant kann darauf automatisieren, ohne dass
irgendwo ein Wert haengen bleiben muesste, der danach wieder zurueckgesetzt
werden will.

`event_types` ist die Liste aller Ausloeser des Xinelum-Katalogs, beim
Einrichten einmal geholt. Sie darf sich zur Laufzeit nicht aendern - Home
Assistant schreibt sie in die Entitaets-Faehigkeiten.
"""

from __future__ import annotations

import logging

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import AUSLOESER_NOTLISTE
from .coordinator import XinelumConfigEntry, XinelumKoordinator
from .entity import XinelumEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: XinelumConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Legt die Ereignis-Entitaet an."""
    async_add_entities([XinelumAusloeserEreignis(entry.runtime_data)])


class XinelumAusloeserEreignis(XinelumEntity, EventEntity):
    """Feuert, wenn Xinelum einen Ausloeser meldet."""

    _attr_icon = "mdi:flash"

    def __init__(self, koordinator: XinelumKoordinator) -> None:
        super().__init__(koordinator, "ausloeser")
        # War der Katalog beim Einrichten nicht lesbar, greift die Notliste.
        # Eine leere `event_types`-Liste waere schlimmer als eine unvollstaendige:
        # dann liesse sich gar nichts automatisieren.
        schluessel = list(koordinator.ausloeser_namen) or list(AUSLOESER_NOTLISTE)
        self._attr_event_types = schluessel

    async def async_added_to_hass(self) -> None:
        """Haengt sich in den Ausloeser-Strom des Koordinators."""
        await super().async_added_to_hass()
        self.async_on_remove(self.coordinator.hoere_ausloeser(self._bei_ausloeser))

    @callback
    def _bei_ausloeser(self, schluessel: str) -> None:
        if schluessel not in self.event_types:
            # Ein Ausloeser, den der Katalog beim Einrichten noch nicht kannte.
            # Nicht werfen: Home Assistant verlangt, dass event_types fest
            # steht, und ein neuer Schluessel ist kein Grund, den Abend zu
            # stoeren. Nach einem Neuladen der Integration ist er dabei.
            _LOGGER.debug(
                "Unbekannter Ausloeser %s, die Integration einmal neu laden",
                schluessel,
            )
            return
        self._trigger_event(
            schluessel,
            {"name": self.coordinator.ausloeser_namen.get(schluessel, schluessel)},
        )
        self.async_write_ha_state()
