# Xinelum für Home Assistant

Xinelum erkennt am Bild, was im Heimkino gerade passiert: Filmstart, Pause,
Abspann, Bildformat, Spielzeit. Diese Integration bringt das als Entitäten
nach Home Assistant, damit Licht, Vorhänge und Leinwand darauf reagieren
können.

**Sie spricht direkt mit der Xinelum-App im Heimnetz.** Kein MQTT-Broker,
kein Cloud-Dienst, kein Server dazwischen.

**[In HACS öffnen](https://my.home-assistant.io/redirect/hacs_repository/?owner=Xinelum&repository=xinelum-homeassistant&category=integration)**

1. Über den Knopf oben in HACS als benutzerdefiniertes Repository hinzufügen
   (Typ *Integration*).
2. Xinelum in HACS installieren.
3. Home Assistant neu starten. Xinelum wird im Heimnetz gefunden.

Anleitung mit Bildern: <https://xinelum.app/integration/>

## Die Integration ist kostenlos. Der Kauf sitzt in der App.

Diese Integration darf jeder herunterladen, installieren und lesen. Sie kostet
nichts und wird nie etwas kosten.

Ob Xinelum den Kinozustand herausgibt, entscheidet in der Xinelum-App der Kauf
**„Erweiterte Smarthome-Anbindung“** oder ein aktives **Xinelum+**, beides
unter *Erweiterungen*. Ohne einen davon antwortet die App zwar, gibt aber
keinen Zustand heraus, und die Integration sagt das im Klartext, statt einen
unbekannten Fehler zu melden.

## Was du brauchst

- Xinelum auf dem Gerät, das dein Kino führt, am besten auf dem Mac. Er
  rechnet immer. Ein iPhone oder iPad antwortet nur, solange Xinelum dort
  geöffnet ist.
- Home Assistant im selben Heimnetz.
- Die Erweiterte Smarthome-Anbindung oder Xinelum+.
- In der App den **Fernstart per Webadresse** (Tab *Automation*). Eine dieser
  Adressen verbindet Home Assistant mit deinem Kino.

## Was du bekommst

Ein Gerät namens **Xinelum** mit sieben Entitäten:

| Entität | Art | Inhalt |
|---|---|---|
| `sensor.xinelum_kinozustand` | Sensor | „Filmstart“, „Pause“, „Abspann Phase 2“ … plus die Merkmale `kinophase` und `quelle` |
| `binary_sensor.xinelum_film_laeuft` | Ja-Nein, `running` | Läuft gerade ein Film |
| `sensor.xinelum_bildformat` | Sensor | 16:9, 21:9, 1.85:1 … |
| `sensor.xinelum_spielzeit` | Sensor, `duration`, Sekunden | Spielzeit laut Player-Overlay |
| `sensor.xinelum_konfidenz` | Sensor, Prozent | Wie sicher die Erkennung war |
| `binary_sensor.xinelum_bildsignal` | Ja-Nein, `connectivity` | Liegt am HDMI-Eingang ein Bild an |
| `event.xinelum_ausloeser` | Ereignis | Feuert bei jedem Auslöser, `event_type` ist der Schlüssel (`filmstart`, `abspann-1`, `format-21-9` …) |

Die Kennungen stehen so fest, wie sie hier stehen: sie hängen nicht an der
Sprache deiner Home-Assistant-Instanz, und Umlaute werden sauber übertragen
(`film_laeuft`, nicht `film_lauft`). Umbenennen darfst du trotzdem jederzeit.

„Film läuft“ und „Bildsignal“ können auch **unbekannt** sein. Meldet sich kein
Sensor mehr, behauptet die Integration nicht, es liefe noch ein Film.

**Sie liest nur.** Xinelum schaltet Beamer, Verstärker und Licht selbst; diese
Integration schickt keinen einzigen Befehl dorthin.

## Einbau

### Mit HACS

1. [In HACS öffnen](https://my.home-assistant.io/redirect/hacs_repository/?owner=Xinelum&repository=xinelum-homeassistant&category=integration), oder in HACS oben rechts *Benutzerdefinierte
   Repositories* wählen und `https://github.com/Xinelum/xinelum-homeassistant`
   eintragen, Typ *Integration*.
2. „Xinelum“ installieren.
3. Home Assistant neu starten.

### Ohne HACS, als Rückfall

1. `xinelum-homeassistant-<version>.zip` von <https://xinelum.app/integration/> laden.
2. Entpacken. Darin liegt genau ein Ordner: `xinelum`.
3. Diesen Ordner nach `config/custom_components/` legen, sodass es am Ende
   `config/custom_components/xinelum/manifest.json` gibt.
4. Home Assistant neu starten.

Gibt es `config/custom_components/` noch nicht, lege den Ordner an. `config`
ist das Verzeichnis, in dem auch deine `configuration.yaml` liegt. Updates
kommen so nicht von selbst; mit HACS schon.

## Einrichten

Meist meldet sich Xinelum von selbst: unter *Einstellungen → Geräte & Dienste*
steht „Xinelum gefunden“. Sonst *Integration hinzufügen → Xinelum*.

Der Dialog hat **ein Feld**: eine Webadresse aus der App. Öffne in der
Xinelum-App den Tab *Automation*, schalte *Fernstart per Webadresse* ein,
halte eine der Adressen gedrückt und kopiere sie. Sie sieht so aus:

```
http://192.168.178.20:47474/xinelum/<schlüssel>/starten
```

Welche der drei Adressen du nimmst, ist egal. Hat Home Assistant Xinelum
schon gefunden, reicht auch der Schlüssel allein.

Gib die Adresse nur Home Assistant. Wer sie kennt, kann dein Kino starten und
den Kinozustand lesen. Erzeugst du in der App eine neue, fragt Home Assistant
dich nach ihr.

## Wenn es nicht klappt

Der Dialog sagt dir, **welcher** Fall vorliegt:

| Meldung | Was zu tun ist |
|---|---|
| „Das ist keine Webadresse von Xinelum.“ | Die Adresse noch einmal aus der App kopieren. |
| „Unter dieser Adresse antwortet nichts.“ | Ist Xinelum auf dem führenden Gerät geöffnet und der Fernstart per Webadresse an? Dasselbe Heimnetz? |
| „Xinelum antwortet, nimmt diesen Schlüssel aber nicht an.“ | Der Schlüssel wurde in der App erneuert. Neue Adresse kopieren. |
| „Xinelum läuft auf diesem Gerät, führt das Kino aber gerade nicht.“ | Die Adresse des Geräts nehmen, das das Kino führt, am besten den Mac. |
| „Xinelum gibt den Kinozustand erst mit dem Kauf …“ | In der Xinelum-App unter *Erweiterungen* die Erweiterte Smarthome-Anbindung oder Xinelum+. Danach im Dialog noch einmal auf *Weiter*. |
| „Unter dieser Adresse antwortet zwar etwas, aber es ist kein Xinelum.“ | Da läuft ein anderer Dienst auf dem Port. |

Fällt die Freischaltung später weg (Erstattung, Kontowechsel, Xinelum+
beendet), werden alle Entitäten **nicht verfügbar**, und Home Assistant zeigt
unter *Reparaturen* den Grund an. Sie bleiben ausdrücklich nicht auf ihrem
letzten Wert stehen.

Für alles Weitere: *Einstellungen → Geräte & Dienste → Xinelum → drei Punkte →
Diagnose herunterladen*. Darin stehen Adresse, ob der Ereignisstrom steht, das
Abfrageintervall und der vollständige Zustand. Der Schlüssel steht dort
**nicht** drin.

## Wie die Daten ankommen

Die App reicht jede Änderung sofort als Ereignisstrom weiter (Server-Sent
Events): ein Filmstart kommt an, wenn er passiert, nicht beim nächsten Abruf.
Steht der Strom nicht, fragt die Integration alle zehn Sekunden nach und baut
ihn im Hintergrund neu auf. Steht er, wird nur noch alle fünf Minuten zur
Sicherheit nachgefasst. Die App meldet sich alle 25 Sekunden mit einem
Lebenszeichen; bleibt es aus, gilt die Leitung als tot.

Der Stand im Strom und der auf Abfrage entstehen an derselben Stelle in der
App. Beide Wege liefern damit dasselbe.

## Automatisieren

```yaml
automation:
  - alias: "Licht aus beim Filmstart"
    triggers:
      - trigger: state
        entity_id: event.xinelum_ausloeser
        attribute: event_type
        to: filmstart
    actions:
      - action: light.turn_off
        target:
          entity_id: light.kino

  - alias: "Licht hoch, wenn der Abspann anfängt"
    triggers:
      - trigger: state
        entity_id: sensor.xinelum_kinozustand
        to: "Abspann Phase 2"
    actions:
      - action: light.turn_on
        target:
          entity_id: light.kino
        data:
          brightness_pct: 40
```

Für „läuft gerade ein Film“ nimm `binary_sensor.xinelum_film_laeuft`, und
denk daran, dass er `unknown` sein kann. Eine Bedingung `is_state(..., 'on')`
ist deshalb sicherer als `not is_state(..., 'off')`.

## Fehler und Wünsche

<https://github.com/Xinelum/xinelum-homeassistant/issues>

## Lizenz

MIT, siehe `LICENSE`. Die Integration ist frei; der Kauf sitzt in der
Xinelum-App.

**Marken:** Der Name und das Logo „Xinelum“ sowie der Ordner `brand/` sind von
der MIT-Lizenz ausgenommen. Sie gehören Frank Müller (Xinelum), die Wortmarke
ist beim DPMA angemeldet. Home Assistant ist eine Marke der Open Home
Foundation. Apple, iPhone, iPad und Mac sind Marken der Apple Inc.
Kein offizielles Projekt von Home Assistant oder der Open Home Foundation,
keine Verbindung zu ihnen oder zu Apple.
