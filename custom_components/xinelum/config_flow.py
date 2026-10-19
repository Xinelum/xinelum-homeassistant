"""Der Einrichtungsdialog.

Ein Feld: eine Webadresse, so wie die App sie im Tab Automation unter
„Fernstart per Webadresse“ zum Kopieren anbietet
(http://<geraet>:47474/xinelum/<schluessel>/starten).
Daraus kommen Adresse, Port und Schluessel; tippen muss niemand etwas.

Die wichtigste Aufgabe dieses Dialogs ist das ERKLAEREN, wenn es nicht klappt:

    adresse_unlesbar      Das ist keine Webadresse von Xinelum.
    nicht_erreichbar      Unter der Adresse antwortet nichts.
    abgelehnt             Xinelum antwortet, nimmt den Schluessel aber nicht.
    ruht                  Xinelum laeuft, fuehrt das Kino aber auf einem anderen Geraet.
    nicht_freigeschaltet  Xinelum antwortet, aber der Kauf fehlt.
    unbekannte_antwort    Da antwortet etwas, aber es ist kein Xinelum.

„nicht_freigeschaltet“ wird der haeufigste Fall sein. Die Integration ist frei
herunterladbar, der Kauf sitzt in der App: die „Erweiterte
Smarthome-Anbindung“ oder ein aktives Xinelum+. Dieser Fall verdient den
besten Text der ganzen Integration. Er steht in `translations/`.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .api import (
    XinelumAbgelehnt,
    XinelumAntwortUnbrauchbar,
    XinelumClient,
    XinelumNichtErreichbar,
    XinelumNichtFreigeschaltet,
    XinelumRuht,
    baue_basis,
)
from .const import CONF_ADRESSE, DOMAIN, STANDARD_PORT, instanzkennung, lies_adresse

_LOGGER = logging.getLogger(__name__)

FEHLER_ADRESSE_UNLESBAR = "adresse_unlesbar"
FEHLER_NICHT_ERREICHBAR = "nicht_erreichbar"
FEHLER_ABGELEHNT = "abgelehnt"
FEHLER_RUHT = "ruht"
FEHLER_NICHT_FREIGESCHALTET = "nicht_freigeschaltet"
FEHLER_UNBEKANNTE_ANTWORT = "unbekannte_antwort"

SCHEMA_ADRESSE = vol.Schema({vol.Required(CONF_ADRESSE): str})


class XinelumConfigFlow(ConfigFlow, domain=DOMAIN):
    """Fuehrt durch die Einrichtung."""

    # 2 seit dem 19.10.2026: Webadresse aus der App statt Adresse und Kennung.
    VERSION = 2

    def __init__(self) -> None:
        self._entdeckt_host: str | None = None
        self._entdeckt_port: int = STANDARD_PORT
        self._entdeckt_kennung: str | None = None

    async def _pruefe(self, daten: dict[str, Any]) -> str | None:
        """Baut die Verbindung testweise auf.

        Antwortet mit dem Fehlerschluessel oder None, wenn alles stimmt.
        """
        client = XinelumClient(
            async_get_clientsession(self.hass),
            baue_basis(daten[CONF_HOST], daten[CONF_PORT]),
            daten[CONF_TOKEN],
        )
        try:
            await client.pruefe_einrichtung()
        except XinelumNichtErreichbar:
            return FEHLER_NICHT_ERREICHBAR
        except XinelumAbgelehnt:
            return FEHLER_ABGELEHNT
        except XinelumRuht:
            return FEHLER_RUHT
        except XinelumNichtFreigeschaltet:
            return FEHLER_NICHT_FREIGESCHALTET
        except XinelumAntwortUnbrauchbar:
            return FEHLER_UNBEKANNTE_ANTWORT
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Eine Webadresse aus der App einfuegen."""
        fehler: dict[str, str] = {}
        if user_input is not None:
            gelesen = lies_adresse(user_input[CONF_ADRESSE])
            if gelesen is None or gelesen[0] is None or gelesen[1] is None:
                fehler["base"] = FEHLER_ADRESSE_UNLESBAR
            else:
                host, port, token = gelesen
                # Ein Haushalt nur einmal: die Kennung haengt am Schluessel,
                # nicht an der Adresse, die sich im Heimnetz aendern darf.
                await self.async_set_unique_id(instanzkennung(token))
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: host, CONF_PORT: port}
                )
                daten = {CONF_HOST: host, CONF_PORT: port, CONF_TOKEN: token}
                grund = await self._pruefe(daten)
                if grund is None:
                    return self.async_create_entry(title="Xinelum", data=daten)
                fehler["base"] = grund

        return self.async_show_form(
            step_id="user", data_schema=SCHEMA_ADRESSE, errors=fehler
        )

    # ------------------------------------------------------------ Discovery

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Xinelum hat sich im Heimnetz gemeldet.

        Die App meldet sich als `_xinelum-ha._tcp`, solange der Fernstart
        per Webadresse an ist und das Geraet das Kino fuehrt. Im TXT steht `id`,
        die Kennung des Haushalts (aus dem Schluessel gerechnet, ohne ihn zu
        verraten).
        """
        host = str(discovery_info.ip_address)
        port = discovery_info.port or STANDARD_PORT
        kennung = discovery_info.properties.get("id") or f"{host}:{port}"

        await self.async_set_unique_id(kennung)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host, CONF_PORT: port})

        self._entdeckt_host = host
        self._entdeckt_port = port
        self._entdeckt_kennung = discovery_info.properties.get("id")
        self.context["title_placeholders"] = {"name": "Xinelum"}
        return await self.async_step_zeroconf_bestaetigen()

    async def async_step_zeroconf_bestaetigen(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Nur noch der Schluessel; Adresse und Port kommen aus dem Fund."""
        fehler: dict[str, str] = {}
        if user_input is not None:
            gelesen = lies_adresse(user_input[CONF_ADRESSE])
            if gelesen is None:
                fehler["base"] = FEHLER_ADRESSE_UNLESBAR
            elif (
                self._entdeckt_kennung is not None
                and instanzkennung(gelesen[2]) != self._entdeckt_kennung
            ):
                # Der Schluessel gehoert zu einem anderen Haushalt.
                fehler["base"] = FEHLER_ABGELEHNT
            else:
                daten = {
                    CONF_HOST: self._entdeckt_host,
                    CONF_PORT: self._entdeckt_port,
                    CONF_TOKEN: gelesen[2],
                }
                grund = await self._pruefe(daten)
                if grund is None:
                    return self.async_create_entry(title="Xinelum", data=daten)
                fehler["base"] = grund

        return self.async_show_form(
            step_id="zeroconf_bestaetigen",
            data_schema=SCHEMA_ADRESSE,
            errors=fehler,
            description_placeholders={"host": self._entdeckt_host or ""},
        )

    # --------------------------------------------------------------- Reauth

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Das Tor nimmt den Schluessel nicht mehr (erneuert in der App)."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Eine neue Webadresse entgegennehmen und pruefen."""
        eintrag = self._get_reauth_entry()
        fehler: dict[str, str] = {}
        if user_input is not None:
            gelesen = lies_adresse(user_input[CONF_ADRESSE])
            if gelesen is None:
                fehler["base"] = FEHLER_ADRESSE_UNLESBAR
            else:
                host, port, token = gelesen
                neu = {CONF_TOKEN: token}
                if host is not None and port is not None:
                    neu |= {CONF_HOST: host, CONF_PORT: port}
                grund = await self._pruefe({**eintrag.data, **neu})
                if grund is None:
                    return self.async_update_reload_and_abort(
                        eintrag,
                        unique_id=instanzkennung(token),
                        data_updates=neu,
                    )
                fehler["base"] = grund

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=SCHEMA_ADRESSE,
            errors=fehler,
            description_placeholders={"host": eintrag.data.get(CONF_HOST, "")},
        )
