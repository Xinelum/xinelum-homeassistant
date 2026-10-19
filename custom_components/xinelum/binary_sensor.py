"""Die zwei Ja-Nein-Entitaeten: laeuft ein Film, liegt ein Bild an.

Beide koennen drei Antworten geben, nicht zwei: ja, nein und "ich weiss es
gerade nicht". Die dritte ist die wichtigste.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import XinelumConfigEntry, XinelumKoordinator
from .entity import XinelumEntity
from .modelle import XinelumZustand


@dataclass(frozen=True, kw_only=True)
class XinelumBinaerBeschreibung(BinarySensorEntityDescription):
    """Ein Ja-Nein-Sensor und die Frage dahinter."""

    wert: Callable[[XinelumZustand], bool | None]


BINAERSENSOREN: tuple[XinelumBinaerBeschreibung, ...] = (
    XinelumBinaerBeschreibung(
        key="film_laeuft",
        translation_key="film_laeuft",
        icon="mdi:play-circle",
        device_class=BinarySensorDeviceClass.RUNNING,
        # `film_laeuft` (nicht `film_laeuft_roh`) ist hier Absicht und der
        # zweite Fehler, den die MQTT-Fassung macht: dort bleibt "Film laeuft"
        # AN, wenn der Sensor wegfaellt, weil der Wert an der Ausloeser-Spur
        # haengt und die auf `filmstart` stehenbleibt. Home Assistant zeigt
        # dann einen laufenden Film in einem Raum, in dem niemand mehr misst -
        # und eine Automatisierung, die daran haengt, laesst das Licht aus.
        # Hier wird daraus None, also "unbekannt". Siehe modelle.sensor_weg.
        wert=lambda z: z.film_laeuft,
    ),
    XinelumBinaerBeschreibung(
        key="bildsignal",
        translation_key="bildsignal",
        icon="mdi:hdmi-port",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        # None, solange der Signalwaechter nichts gemessen hat (kein Grabber
        # eingerichtet). Kein Bild ist etwas anderes als keine Messung.
        wert=lambda z: z.bildsignal,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: XinelumConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Legt die Ja-Nein-Sensoren an."""
    koordinator = entry.runtime_data
    async_add_entities(
        XinelumBinaerSensor(koordinator, beschreibung)
        for beschreibung in BINAERSENSOREN
    )


class XinelumBinaerSensor(XinelumEntity, BinarySensorEntity):
    """Ein Ja-Nein-Wert aus dem Kinozustand."""

    entity_description: XinelumBinaerBeschreibung

    def __init__(
        self, koordinator: XinelumKoordinator, beschreibung: XinelumBinaerBeschreibung
    ) -> None:
        super().__init__(koordinator, beschreibung.key)
        self.entity_description = beschreibung

    @property
    def is_on(self) -> bool | None:
        """An, aus - oder None, wenn Xinelum es gerade nicht weiss."""
        zustand = self.zustand
        if zustand is None:
            return None
        return self.entity_description.wert(zustand)
