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


def swap_dongle_for_konik(konik: bool, params) -> None:
  """Stash the current DongleId, then load the saved DongleId if it exists.
  If not, remove the DongleId to trigger registration with the respective API on next boot."""
  current = params.get("DongleId")
  old_dongle_id = "KonikDongleId" if not konik else "CommaDongleId"
  new_dongle_id = "CommaDongleId" if not konik else "KonikDongleId"

  if current:
    _write(old_dongle_id, current)

  saved = _read(new_dongle_id)
  if saved:
    params.put("DongleId", saved)
  else:
    params.remove("DongleId")
