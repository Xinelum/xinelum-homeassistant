"""Gemeinsamer Unterbau aller Xinelum-Entitaeten.

Hier stehen die drei Dinge, die eine Entitaet erst zu einer ordentlichen
Entitaet machen: eine stabile `unique_id`, ein `DeviceInfo`, unter dem alles
als EIN Geraet zusammensteht, und eine vorhersagbare Kennung.

DIE KENNUNG IST DER GRUND, WARUM ES DIESE DATEI GIBT.

Home Assistant baut die Entitaets-Kennung normalerweise aus Geraetename plus
Entitaetsname und schiebt das Ergebnis durch `slugify`. Bei deutschen Namen
kommt dabei Unfug heraus, und zwar nachweislich - ueber MQTT heissen die
Entitaeten heute:

    binary_sensor.xinelum_film_lauft      ("läuft" ohne ae)
    event.xinelum_ausloser                ("Auslöser" ohne oe)

Das ist keine Kleinigkeit. Diese Kennungen stehen in jeder Automatisierung,
und wer sie tippt, tippt sie falsch. Ausserdem haengen sie an der Sprache der
Home-Assistant-Instanz: dieselbe Integration erzeugt auf Deutsch andere
Kennungen als auf Englisch.

Deshalb legt jede Entitaet ihre Kennung selbst fest (`kennung`) und gibt sie
ueber `suggested_object_id` zurueck. Home Assistant sieht das ausdruecklich
vor; die Kern-Integration `aosmith` macht es aus demselben Grund. Ergebnis:

    binary_sensor.xinelum_film_laeuft
    event.xinelum_ausloeser

Sauber transliteriert, gleich in jeder Sprache, in der README dokumentiert.
Der ANGEZEIGTE Name bleibt davon unberuehrt und kommt weiter aus
`translations/`; wer die Entitaet umbenennt, behaelt seinen Namen ueber jeden
Neustart, weil die `unique_id` sich nie aendert.
"""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import XinelumKoordinator
from .modelle import XinelumZustand


class XinelumEntity(CoordinatorEntity[XinelumKoordinator]):
    """Basis aller Entitaeten dieser Integration."""

    _attr_has_entity_name = True

    def __init__(self, koordinator: XinelumKoordinator, kennung: str) -> None:
        super().__init__(koordinator)
        self.kennung = kennung
        eintrag = koordinator.config_entry
        # Der Config-Entry ist das einzige, was Xinelum stabil vergibt und was
        # eine Adressaenderung ueberlebt. An der Adresse haengen hiesse: neue
        # IP, neue Entitaeten, alle Automatisierungen kaputt.
        self._attr_unique_id = f"{eintrag.entry_id}_{kennung}"
        self._attr_translation_key = kennung
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, eintrag.entry_id)},
            name="Xinelum",
            manufacturer="Xinelum",
            model="Heimkino-Steuerung",
            configuration_url=str(koordinator.client.basis),
        )

    @property
    def suggested_object_id(self) -> str | None:
        """Die Kennung, unabhaengig von Sprache und Umlauten."""
        return self.kennung

    @property
    def zustand(self) -> XinelumZustand | None:
        """Der aktuelle Kinozustand, oder None wenn gerade keiner gilt."""
        if not self.coordinator.last_update_success or self.coordinator.data is None:
            return None
        return self.coordinator.data.zustand
