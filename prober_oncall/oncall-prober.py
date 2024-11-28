#Измененный код с семинара

import sys
import logging
import requests
import signal
import time
import random

from prometheus_client import start_http_server, Gauge, Counter

PROBER_GET_SEARCH_INFO_TOTAL = Counter(
    "prober_get_search_info_total", "Total count of runs the search request oncall API"
)

PROBER_GET_SEARCH_INFO_SUCCESS_TOTAL = Counter(
    "prober_get_search_info_success_total", "Total count of success runs search request"
)

PROBER_GET_SEARCH_INFO_FAIL_TOTAL = Counter(
    "prober_get_search_info_fail_total", "Total count of failed runs search request"
)

PROBER_GET_SEARCH_INFO_DURATION_SECONDS = Gauge(
    "prober_get_search_info_duration_seconds", "Duration in seconds of runs the get search request"
)

def get_random_string():
    return ''.join(random.choice("QWERTYUIOPASDFGHJKLZXCVBNM1234567890") for _ in range(random.randint(3,10)))

class Config(object):
    oncall_exporter_api_url = "http://oncall:8080"
    oncall_exporter_scrape_interval = 30
    oncall_exporter_metrics_port = 1238

class OncallProberClient:
    def __init__(self, config):
        self.oncall_api_url = config.oncall_exporter_api_url

    def probe(self):
        PROBER_GET_SEARCH_INFO_TOTAL.inc()

        start = time.perf_counter()
        req = None

        try:
            req = requests.get(f"{self.oncall_api_url}/api/v0/search?keyword={get_random_string()}")
            logging.info(f"Request result: {req}")
        except Exception as err:
            logging.error(err)
            PROBER_GET_SEARCH_INFO_FAIL_TOTAL.inc()

        if req and req.status_code == 200:
            PROBER_GET_SEARCH_INFO_SUCCESS_TOTAL.inc()
        else:
            PROBER_GET_SEARCH_INFO_FAIL_TOTAL.inc()

        duration = time.perf_counter() - start
        PROBER_GET_SEARCH_INFO_DURATION_SECONDS.set(duration)

def setup_logging():
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s:%(message)s"
    )

def main():
    config = Config()
    setup_logging()

    logging.info(f"Start prober, port: {config.oncall_exporter_metrics_port}")
    start_http_server(config.oncall_exporter_metrics_port)
    client = OncallProberClient(config)
    while True:
        logging.info(f"Run prober")
        client.probe()

        logging.info(
            f"waiting {config.oncall_exporter_scrape_interval} s"
        )

        time.sleep(config.oncall_exporter_scrape_interval)

def terminate(signal, frame):
    print("Terminating")
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGTERM, terminate)
    main()
