"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import os

# Imported by manager.py before anything that reads API_HOST / ATHENA_HOST, so only use the standard library here.

KONIK_API_HOST = "https://api.konik.ai"
KONIK_ATHENA_HOST = "wss://athena.konik.ai"

# New Params keys need the params library rebuilt, which prebuilt releases can't do, so the state lives in plain files
KONIK_DIR = "/data/konik_api"
ENABLED_FILE = os.path.join(KONIK_DIR, "KonikApi")


def is_konik_enabled() -> bool:
  return os.path.isfile(ENABLED_FILE)


def set_konik_enabled(enabled: bool) -> None:
  os.makedirs(KONIK_DIR, exist_ok=True)
  if enabled:
    open(ENABLED_FILE, "w").close()
  elif os.path.isfile(ENABLED_FILE):
    os.remove(ENABLED_FILE)


def apply_konik_env() -> None:
  """Override API_HOST / ATHENA_HOST environment variables if Konik API is enabled."""
  konik = is_konik_enabled()
  if konik:
    os.environ.setdefault("API_HOST", KONIK_API_HOST)
    os.environ.setdefault("ATHENA_HOST", KONIK_ATHENA_HOST)
  _reset_pairing_cache_on_backend_change("konik" if konik else "comma")


def konik_active() -> bool:
  """Whether this process talks to Konik, i.e. the backend applied at boot rather than the toggle's pending state."""
  return os.getenv("API_HOST", "").rstrip("/") == KONIK_API_HOST


def get_pairing_host() -> str:
  return "stable.konik.ai" if konik_active() else "connect.comma.ai"


def get_pairing_backend_name() -> str:
  return "Konik" if konik_active() else "comma.ai"


def _reset_pairing_cache_on_backend_change(backend: str) -> None:
  # The UI caches the old backend's pairing state and only replaces it on a successful fetch, so drop it
  if _read("LastBackend") == backend:
    return

  from openpilot.common.params import Params
  params = Params()
  for key in ("PrimeType", "PairingProvider", "PairingEmail"):
    params.remove(key)
  _write("LastBackend", backend)


def _read(name: str) -> str | None:
  try:
    with open(os.path.join(KONIK_DIR, name)) as f:
      return f.read().strip() or None
  except FileNotFoundError:
    return None


def _write(name: str, value: str) -> None:
  os.makedirs(KONIK_DIR, exist_ok=True)
  with open(os.path.join(KONIK_DIR, name), "w") as f:
    f.write(value)


def _persisted_comma_dongle_id() -> str | None:
  try:
    with open("/persist/comma/dongle_id") as f:
      return f.read().strip() or None
  except OSError:
    return None


def sync_konik_dongle_id(params) -> None:
  """Konik needs its own registration, but register() keeps comma's dongle id from /persist,
  so register with Konik once and switch DongleId between the two backends' ids."""
  from openpilot.system.athena.registration import register, UNREGISTERED_DONGLE_ID

  current = params.get("DongleId")
  comma_dongle_id = _read("CommaDongleId") or _persisted_comma_dongle_id()
  konik_dongle_id = _read("KonikDongleId")
  if konik_dongle_id == comma_dongle_id:
    konik_dongle_id = None  # stashed by an older version that never registered with Konik

  if konik_active():
    if current not in (None, UNREGISTERED_DONGLE_ID, konik_dongle_id):
      _write("CommaDongleId", current)
    if konik_dongle_id is None:
      new_dongle_id = register(show_spinner=True, register_konik=True)
      if new_dongle_id not in (None, UNREGISTERED_DONGLE_ID):
        konik_dongle_id = new_dongle_id
        _write("KonikDongleId", konik_dongle_id)
    if konik_dongle_id is not None and current != konik_dongle_id:
      params.put("DongleId", konik_dongle_id, block=True)
  elif konik_dongle_id is not None and current == konik_dongle_id:
    if comma_dongle_id:
      params.put("DongleId", comma_dongle_id, block=True)
    else:
      params.remove("DongleId")  # register() registers with comma again
