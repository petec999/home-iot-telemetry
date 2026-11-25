# Home Assistant · HaierPi 1.4.5_3

## Aktualny sposób wdrożenia — bez dodatkowych zakładek

Zgodnie z rzeczywistym układem pulpitu `Dom`, użytkownik chce wszystkie
funkcje HaierPi **wewnątrz istniejącego widoku „Pompa ciepła”**, a czujnik
temperatury w domu — w widoku **„Klimatyzacja”**.

W dodatku **Terminal & SSH Home Assistant** (nie na NanoPi `root@HaierPi`)
uruchom jedną komendę:

```sh
curl -fsSL https://raw.githubusercontent.com/petec999/home-iot-telemetry/main/home_assistant/merge-haierpi-panel.py | python3 -
```

Skrypt najpierw zapisuje pełną kopię poprzedniego pulpitu w
`/config/haierpi-lovelace-backups/`, a następnie modyfikuje konfigurację
przez oficjalne WebSocket API Lovelace. Nie zmienia bezpośrednio `.storage`,
`configuration.yaml` ani żadnej usługi NanoPi.

Działania:
- zachowanie zakładki **Pompa ciepła** ze sterowaniem, bilansem, pomiarami,
  wykresami oraz unikatowymi źródłowymi czujnikami;
- wstawienie **8 liczników cykli/defrostów i 6 pochodnych parametrów obiegu**,
  z wykresami i pomocniczą oceną dostępności;
- usunięcie starego wskaźnika `sensor.haier_cop_chwilowy` (obecnie
  `unavailable`) i jego trzech pustych wykresów; zachowanie działającego
  `sensor.haier_bilans_cop_dobowy` oraz obliczeń COP w pozostałych kartach;
- usunięcie wielokrotnie pokazywanych w tabelach tych samych encji. Wykresy
  mogą celowo powtarzać encje użyte w bieżącym odczycie;
- przeniesienie osobnej karty „temperatura dom” do **Klimatyzacja**: Zigbee
  temperatura, wilgotność i oświetlenie. Temperatura trafia także na
  istniejący 48-godzinny wykres klimatyzacji;
- usunięcie wyłącznie czterech tymczasowych zakładek
  `haierpi-przeglad`, `haierpi-cykle`, `haierpi-obieg`,
  `haierpi-bilans`. Pozostałe zakładki (Fotowoltaika, CWU, kamery,
  światła/rolety itd.) są zachowane.

Instalator nie wymaga restartu Home Assistant. Jest idempotentny i w razie
braku uprawnień lub nieoczekiwanej struktury pulpitu przerywa działanie zamiast
nadpisywać konfigurację. Dla terminala HA wymagane są uprawnienia API
(SUPERVISOR_TOKEN). Użycie na NanoPi nie wprowadza zmian.

Sprawdzenie: GitHub Actions uruchamia test migracji na sztucznym, anonimowym
pulpicie oraz test zgodności wszystkich 14 encji z wydaniem
[`petec999/hpi v1.4.5_1`](https://github.com/petec999/hpi/releases/tag/v1.4.5_1).

## Wcześniejsza instalacja i pliki źródłowe

Dawna komenda `add-haierpi-views.py` dodaje cztery **oddzielne zakładki**,
więc nie należy jej ponownie uruchamiać po konsolidacji. Pozostaje w historii
repozytorium na potrzeby odtwarzania, ale obecnie zalecana jest powyższa
`merge-haierpi-panel.py`.

Źródła wszystkich kart to:
- `dashboards/haierpi-centrum-1.4.5_1.yaml`
- `dashboards/haierpi-centrum-1.4.5_1.json`
- `dashboards/haier-diagnostyka-view.yaml`


## Pompa ciepła · watchdog MQTT v2

Po instalacji watchdogu z [HaierPi 1.4.5_3](https://github.com/petec999/hpi/releases/tag/v1.4.5_3) uruchom w terminalu HA:

```sh
curl -fsSL https://raw.githubusercontent.com/petec999/home-iot-telemetry/main/home_assistant/update-haier-watchdog-panel.py | python3 -
```

Skrypt dodaje jedną kartę „HaierPi · komunikacja MQTT” w istniejącym widoku `pompa-ciepla`. Wymaga encji `sensor.haierpi_mqtt_heartbeat`, zapisuje kopię pulpitu, nie zmienia innych widoków i nie wymaga restartu. Opcja `python3 - --dry-run` sprawdza zgodność bez zapisu.

Karta pokazuje świeżość odbioru heartbeat w HA i czas ostatniej zmiany. Watchdog na NanoPi sprawdza niezależnie potwierdzenie REST; ostrzega po 90 s, alarmuje po 180 s i może zlecić ograniczony reconnect MQTT. Powiadomienia trwałe przez REST są kasowane po potwierdzonym powrocie. Jeśli API HA jest niedostępne, nie można wysłać powiadomienia. Karta nie zastępuje kontroli świeżości R141/R241. Normalne działanie watchdogu v2 i karty potwierdzono 25.11.2026; sprzętowe testy awarii i rebootu pozostają otwarte.

## Klimatyzacja · Midea Cloud Control 0.2.1

Po instalacji integracji [Midea Cloud Control](https://github.com/petec999/midea-cloud-control)
uruchom w terminalu Home Assistant:

```sh
curl -fsSL https://raw.githubusercontent.com/petec999/home-iot-telemetry/main/home_assistant/update-midea-panel.py | python3 -
```

Instalator wyszukuje istniejący klimatyzator w widoku `klimatyzacja` i dopasowuje
nowe encje na podstawie rejestru urządzeń i unikalnych identyfikatorów. Nie
dodaje innych urządzeń z konta. Pomija wyłączone lub nieobecne encje.
Dla Jaśminowej pokazuje tylko potwierdzone przełączniki Turbo i Sleep; usuwa
ECO i LED z pulpitu (brak obsługi przez aplikację producenta), również gdy
encje pozostają w rejestrze HA. Dodaje dwa sensory temperatury, warunki
w domu, wykres 24 h oraz diagnostykę filtra i błędów. Zachowuje istniejący
termostat i pozostałe widoki. Nie wysyła komend do klimatyzatora ani pompy ciepła.

Przed zapisem tworzy pełną kopię pulpitu w `/config/lovelace-backups/`.
W przypadku braku wymaganych encji temperatury albo niejednoznacznego
urządzenia przerywa bez zapisu. Opcja `python3 - --dry-run` pozwala sprawdzić
plan bez zapisu. Restart Home Assistant nie jest potrzebny.

Testy offline: `python3 -m unittest discover -s tests -p test_midea_panel.py -v`.
