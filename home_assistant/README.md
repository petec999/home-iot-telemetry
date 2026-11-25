# Home Assistant · HaierPi 1.4.5_1

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

