"""Populate the dev database with realistic demo activity by replaying the milestone acceptance scenarios
through the real API (CAS ticket lifecycle, NSWS->CONN-4, FTC stages 1-5, comm cert, control-room shift with codes,
trippings, availability, alerts). Run after seeding:

    python -m app.db.seed --reset
    python -m scripts.demo_data
"""
import os
import sys
from pathlib import Path

os.environ["OMS_CAPTCHA_ENABLED"] = "false"
os.environ["OMS_RATE_LIMIT"] = "100000/minute"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from tests import conftest  # noqa: E402
from tests import test_m2_portal_cas as m2, test_m3_lifecycle as m3, test_m4_outage_suite as m4  # noqa: E402

SCENARIOS = [m2.test_severity1_ticket_full_lifecycle, m3.test_nsws_connectivity_with_nldc_shift_and_conn4, m3.test_fnc_registration_consents_and_letter,
             m3.test_ftc_stage_1_to_5_creates_elements_enabled_for_realtime, m3.test_comm_cert_two_stages, m4.test_control_room_end_to_end,
             m4.test_hv_batch_codes_and_re_single_window, m4.test_alerts_and_sps]


def main() -> None:
    import logging

    logging.getLogger().setLevel(logging.WARNING)
    for name in ("httpx", "oms.notifier", "oms.nsws"):
        logging.getLogger(name).setLevel(logging.WARNING)
    with TestClient(app) as client:
        auth = lambda u, **kw: conftest.login(client, u, **kw)  # noqa: E731
        for fn in SCENARIOS:
            try:
                fn(client, auth)
                print("OK  ", fn.__name__)
            except Exception as e:  # noqa: BLE001
                print("SKIP", fn.__name__, "-", str(e)[:120])


if __name__ == "__main__":
    main()
