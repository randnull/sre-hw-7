import sys
import logging
import requests
import signal
import time
from datetime import datetime

import mysql.connector

class Config(object):
    prometheus_api_url = "http://prometheus-service:9090"
    scrape_interval = 60
    db_host = "oncall-mysql"
    db_port = 3306
    db_user = "root"
    db_password = "1234"


class Prometheus:
    def __init__(self, config: Config):
        self.prometheus_api_url = config.prometheus_api_url

    def get_value_by_metric(self, query, time, default):
        try:
            response = requests.get(
                self.prometheus_api_url + '/api/v1/query', 
                params={'query': query, 'time': time}
            )

            if not response:
                return default

            content = response.json()

            if not content:
                return default

            if len(content['data']['result']) == 0:
                return default

            return content['data']['result'][0]['value'][1]
        except Exception as error:
            logging.error(error)
            return default


def setup_logging():
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s"
    )


class Mysql:
    def __init__(self, config: Config):
        logging.info('starting connect to database')
        self.connection = mysql.connector.connect(host=config.db_host, user=config.db_user, passwd=config.db_password, auth_plugin='mysql_native_password')
        self.table_name = 'indicators'

        logging.info('starting init database')

        cursor = self.connection.cursor()
        cursor.execute('CREATE DATABASE IF NOT EXISTS sla')
        cursor.execute('USE sla')

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS indicators (
            datetime datetime not null default NOW(),
            name varchar(255) not null,
            slo float(4) not null,
            value float(4) not null,
            is_bad bool not null default false
            )
        """
        )

    def save_ind(self, name, slo, value, is_bad=False, current_time=None):
        logging.info('starting save data')
        cursor = self.connection.cursor()
        sql_request_str = "INSERT INTO indicators (datetime, name, slo, value, is_bad) VALUES (%s, %s, %s, %s, %s)"

        cursor.execute(sql_request_str, (current_time, name, slo, value, is_bad))
        self.connection.commit()
        

        # пример вывода что в базе
        # cursor.execute("SELECT * FROM indicators")

        # rows = cursor.fetchall()

        # for row in rows:
        #     print(row)
        logging.info('data saved!')


def main():
    config = Config()
    setup_logging()
    db = Mysql(config)
    prom = Prometheus(config)

    logging.info("Starting SLA checker")

    while True:
        logging.info("Run prober")

        unixtimestamp = int(time.time())
        date_format = datetime.utcfromtimestamp(unixtimestamp).strftime('%Y-%m-%d %H:%M:%S')

        # успех
        value = prom.get_value_by_metric(
            'increase(prober_get_search_info_success_total[1m])', unixtimestamp, 0)
        value = int(float(value))
        db.save_ind(name='prober_get_search_info_success_total',
                          slo=1, value=value, is_bad=value < 1, current_time=date_format)

        # fail
        value = prom.get_value_by_metric(
            'increase(prober_get_search_info_fail_total[1m])', unixtimestamp, 100)
        value = int(float(value))
        db.save_ind(name='prober_get_search_info_fail_total',
                          slo=0, value=value, is_bad=value > 0, current_time=date_format)

        #время выполнения
        value = prom.get_value_by_metric(
            'prober_get_search_info_duration_seconds', unixtimestamp, 2)
        value = float(value)
        db.save_ind(name='prober_get_search_info_duration_seconds',
                          slo=0.1, value=value, is_bad=value > 0.1, current_time=date_format)

        logging.info(f"Waiting {config.scrape_interval} seconds for next loop")
        time.sleep(config.scrape_interval)

def terminate(signal, frame):
    logging.info("Terminating")
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGTERM, terminate)
    main()
