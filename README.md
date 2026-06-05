# 🍓 Raspberry Pi Probe Kit

*Набор одноразовых Python-скриптов для SSH-доступа к Raspberry Pi: проверка камеры, снятие снимков и MAVLink-диагностика полётного контроллера.*

![Python](https://img.shields.io/badge/Python-3.x-3776AB?logo=python&logoColor=white)
![Paramiko](https://img.shields.io/badge/SSH-Paramiko-2C3E50?logo=openssh&logoColor=white)
![MAVLink](https://img.shields.io/badge/MAVLink-pymavlink-FF6F00)
![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-3-C51A4A?logo=raspberrypi&logoColor=white)

---

## ✨ Что делает

Это не приложение, а коллекция небольших скриптов-проб для работы с конкретным
Raspberry Pi 3 (по умолчанию `192.168.11.1`, пользователь `pi`). Скрипты решают
три задачи:

- **SSH-доступ** — перебор связок логин/пароль через `paramiko`, чтобы найти
  рабочую комбинацию.
- **Камера** — подключение по SSH и диагностика камеры (libcamera / vcgencmd /
  `/dev/video*` / V4L2 / dmesg), запись лог-файла на хост при её наличии, а также
  съёмка кадров через `raspistill` с забором по SFTP.
- **Полётный контроллер (PX4/ArduPilot)** — серия MAVLink-проб через `pymavlink`:
  поиск heartbeat, телеметрия, preflight-проверки, стендовый ARM (винты сняты!) и
  чтение nsh-консоли через `SERIAL_CONTROL`.

> Цель проекта (см. `CLAUDE.md`) — подключиться по SSH к Pi, проверить камеру и
> сохранить лог её статуса. `CLAUDE.md` — это рабочий **план**, а не документация
> готового кода. MAVLink-скрипты добавлены позже для диагностики дрона на базе той
> же Pi (Clover/Pixhawk).

---

## 🛠 Стек

- **Python 3.x**
- **paramiko** — SSH/SFTP-клиент (камера, авторизация, деплой скриптов)
- **pymavlink** — MAVLink-связь с полётным контроллером (запускается на самой Pi)
- Утилиты Raspberry Pi OS на стороне устройства: `libcamera-hello`, `vcgencmd`,
  `raspistill`, `v4l2-ctl`

---

## 🚀 Запуск

Скрипты делятся на два типа: **локальные** (запускаются на Windows-машине, идут к
Pi по SSH через paramiko) и **бортовые** (`mav_*.py` — работают на самой Pi и
требуют `pymavlink`).

```powershell
# 1. Виртуальное окружение (на управляющей машине)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Зависимости (requirements.txt в репозитории нет)
pip install paramiko

# 3. Локальные скрипты — идут к Pi по SSH
python probe_auth.py        # подобрать рабочую связку логин/пароль
python check_camera.py      # проверить камеру и записать лог на Pi
python grab_snapshots.py    # снять 3 кадра и забрать по SFTP в .\snapshots\

# 4. MAVLink-диагностика: run_probe.py заливает mav_probe.py на Pi и запускает
python run_probe.py                 # по умолчанию деплоит mav_probe.py
python run_probe.py mav_telemetry.py
```

`mav_*.py` рассчитаны на запуск **на самой Raspberry Pi** (нужен `pymavlink` и
доступ к `/dev/ttyACM*`). Их можно доставить и выполнить через `run_probe.py`
либо вручную скопировать на устройство.

> ⚠️ **Интерактивный SSH запускает пользователь сам**, например:
> `ssh pi@192.168.11.1`. Скрипты используют парольную аутентификацию (хост,
> логин и пароль заданы константами в начале каждого файла — поправьте под себя).

> ⚠️ `mav_arm.py` / `mav_reboot_arm.py` физически **армят** полётный контроллер.
> Запускайте **только со снятыми винтами**.

---

## 📂 Скрипты

| Скрипт | Что делает |
|---|---|
| `probe_auth.py` | Перебирает несколько связок логин/пароль по SSH, ищет рабочую (включая keyboard-interactive). |
| `check_camera.py` | Подключается по SSH, прогоняет набор проверок камеры (libcamera/vcgencmd/`/dev/video*`/V4L2/dmesg), пишет лог-статус на Pi и локальный дамп. |
| `grab_snapshots.py` | Делает N снимков через `raspistill` и забирает их по SFTP в `snapshots/`, чистит `/tmp` на Pi. |
| `run_probe.py` | Локальный драйвер: заливает указанный скрипт на Pi по SSH (base64) и запускает, стримит вывод обратно. |
| `mav_probe.py` | Ищет полётный контроллер по MAVLink (serial/UDP/TCP), ждёт HEARTBEAT, печатает автопилот/тип/версию ПО. |
| `mav_telemetry.py` | Запрашивает потоки данных PX4 и выводит батарею/нагрузку, GPS, attitude, VFR_HUD и режим полёта. |
| `mav_prearm.py` | READ-ONLY preflight: режим/состояние, STATUSTEXT и здоровье сенсоров из `SYS_STATUS`. Не армит. |
| `mav_arm.py` | Стендовый ARM-тест PX4: ослабляет RC/GPS/USB-проверки, переходит в STABILIZED, армит, читает телеметрию, разармит. |
| `mav_arm_reason.py` | Шлёт ARM и ловит точную причину отказа PX4 (STATUSTEXT + COMMAND_ACK). |
| `mav_reboot_arm.py` | Перезагружает полётный контроллер, ждёт переинициализации и повторяет стендовый ARM. |
| `mav_shell_check.py` | Открывает nsh-консоль PX4 через `SERIAL_CONTROL` и гоняет диагностику (`commander check`, `ekf2 status`…). READ-ONLY. |
| `mav_shell_check2.py` | Снимает полный вывод `commander check` и `commander status` из nsh-консоли. READ-ONLY. |
| `pi_usbcheck.py` | Локально на Pi проверяет, видит ли она Pixhawk (`/dev/ttyACM*`, `lsusb`, `dmesg`). |

---

<sub>Одноразовые рабочие скрипты для конкретного стенда. Параметры подключения зашиты в код — адаптируйте под своё устройство.</sub>
