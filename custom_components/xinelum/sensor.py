"""Die vier Mess-Entitaeten: Kinozustand, Bildformat, Spielzeit, Konfidenz."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import XinelumConfigEntry, XinelumKoordinator
from .entity import XinelumEntity
from .modelle import XinelumZustand


@dataclass(frozen=True, kw_only=True)
class XinelumSensorBeschreibung(SensorEntityDescription):
    """Ein Sensor und die Frage, die er an den Kinozustand stellt."""

    wert: Callable[[XinelumZustand], StateType]
    merkmale: Callable[[XinelumZustand], dict[str, Any]] | None = None


SENSOREN: tuple[XinelumSensorBeschreibung, ...] = (
    XinelumSensorBeschreibung(
        key="kinozustand",
        translation_key="kinozustand",
        icon="mdi:movie-open",
        wert=lambda z: z.kinozustand,
        # Kinophase und Quelle haengen als Merkmale daran, statt zwei weitere
        # Entitaeten zu erzeugen. Genau so macht es die MQTT-Fassung.
        merkmale=lambda z: {"kinophase": z.kinophase, "quelle": z.quelle},
    ),
    XinelumSensorBeschreibung(
        key="bildformat",
        translation_key="bildformat",
        icon="mdi:aspect-ratio",
        # Kein erkanntes Format heisst None und damit "unbekannt" - der
        # native Weg. Die MQTT-Fassung schreibt hier das WORT "unbekannt",
        # weil MQTT eine leere Nutzlast sonst als gueltigen Zustand nimmt.
        # Dieselbe Bedeutung, ohne den Umweg.
        wert=lambda z: z.bildformat,
    ),
    XinelumSensorBeschreibung(
        key="spielzeit",
        translation_key="spielzeit",
        icon="mdi:timer-outline",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        # HIER LAG DER TEURE FEHLER DER MQTT-FASSUNG. Dort stand im
        # value_template `'none'` statt `'None'`; Home Assistant nimmt das als
        # gewoehnliche Zeichenkette, scheitert an der Umrechnung in eine Zahl
        # und laesst die Entitaet auf ihrem ALTEN Wert stehen. In Python gibt
        # es diesen Fehler nicht: hier steht ein echtes None, und ein Test
        # nagelt fest, dass es auch wirklich None ist.
        wert=lambda z: z.spielzeit_s,
    ),
    XinelumSensorBeschreibung(
        key="konfidenz",
        translation_key="konfidenz",
        icon="mdi:target",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        wert=lambda z: z.konfidenz_prozent,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: XinelumConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Legt die Sensoren an."""
    koordinator = entry.runtime_data
    async_add_entities(
        XinelumSensor(koordinator, beschreibung) for beschreibung in SENSOREN
    )


class XinelumSensor(XinelumEntity, SensorEntity):
    """Ein Wert aus dem Kinozustand."""

    entity_description: XinelumSensorBeschreibung

    def __init__(
        self, koordinator: XinelumKoordinator, beschreibung: XinelumSensorBeschreibung
    ) -> None:
        super().__init__(koordinator, beschreibung.key)
        self.entity_description = beschreibung

    @property
    def native_value(self) -> StateType:
        """Der Wert - oder None, wenn es gerade keinen gibt."""
        zustand = self.zustand
        if zustand is None:
            return None
        return self.entity_description.wert(zustand)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Zusaetzliche Merkmale, heute nur beim Kinozustand."""
        zustand = self.zustand
        if zustand is None or self.entity_description.merkmale is None:
            return None
        return self.entity_description.merkmale(zustand)
