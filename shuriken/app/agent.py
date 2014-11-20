#!/usr/bin/python
# -*- coding: utf-8 -*-

import time
import subprocess
import argparse
import logging
import socket
from urllib import urlencode
import json
import os.path as op
from config import LOG_PATH, HTTP_TIMEOUT
import requests
import re


def setup_logging(filename=None):
    logging.basicConfig(
        format=u'%(asctime)s %(levelname)s [%(name)s] %(message)s',
        level=logging.DEBUG,
        filename=filename or LOG_PATH
    )


logger = logging.getLogger('agent-{}'.format(socket.getfqdn()))
logger.addHandler(logging.StreamHandler())


class ForbiddenCheckError(Exception):

    """ForbiddenCheckError. Raise when forbidden MonitoringCheck command is
    found """

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class MonitoringCheck(object):

    """Monitoring check object"""

    STOP_COMMANDS_REGEXP = re.compile(
        r'rm(dir)? .*|sudo .*|df .*|dd .*|cp .*|mv .*'
    )

    def __init__(self, hostname, service, command, is_mock=False):
        """

        :param hostname:
        :param service:
        :param command:
        :param is_mock: for tests
        """
        logger.debug(
            "Registered new MonitoringCheck '{}' --> '{}'".format(service, command))
        self.hostname = hostname
        self.service = service
        self.command = command
        self.ts = None
        self.is_mock = is_mock

    def __repr__(self):
        return "<%s(%s, %s)>" % (
            self.__class__.__name__, self.hostname, self.service)

    @staticmethod
    def stop_commands_check(full_command):
        match = MonitoringCheck.STOP_COMMANDS_REGEXP.search(full_command)
        if match:
            raise ForbiddenCheckError("Found stop command pattern: {}. "
                                      "Stop process".format(match))
        return True

    def execute(self):
        """Execute linux command via subprocess

        :return: dict result
        """
        MonitoringCheck.stop_commands_check(self.command)
        logger.info("Execute check '{}' --> '{}'".format(self.service, self.command))
        self.ts = int(time.time())
        result_params = dict(
            service_description=self.service,
            host_name=self.hostname,
            time_stamp=self.ts,
            output='',
            return_code=-99
        )

        if self.is_mock:
            logger.debug('Execute as a mock')
            result_params['output'] = 'Mock result'
            return MonitoringCheckResult(result_params)

        # Run subprocess command and read return code then send it to
        # monitoring server
        try:
            p = subprocess.Popen(self.command, shell=True,
                                 stdout=subprocess.PIPE)
            output, err = p.communicate()
        except Exception as err:
            logger.error(err)
        else:
            logger.info("Check '{}' done.".format(self.service))
            result_params['output'] = output
            result_params['return_code'] = p.returncode
            return MonitoringCheckResult(result_params)


class MonitoringCheckResult(object):

    """MonitoringCheck result container.
    More information here: https://github.com/shinken-monitoring/mod-ws-arbiter
    """

    def __init__(self, data):
        self.data = data

        self.service_description = data['service_description']
        self.host_name = data['host_name']
        self.time_stamp = data['time_stamp']
        self.output = data['output']
        self.return_code = data['return_code']

    def __unicode__(self):
        return u'MonitoringCheckResult({}:{}:{})'.format(
            self.host_name, self.service_description, self.return_code)

    def get_url_encoded_string(self):
        return urlencode(self.data)

    @property
    def is_success(self):
        return self.return_code == 0

    @property
    def is_warning(self):
        return self.return_code == 1

    @property
    def is_critical(self):
        return self.return_code == 2


class Config(object):

    """Config object. For more information about format see
    example_config.json"""

    def __init__(self, **kwargs):
        """ Init following parameters:
            * server settings (url, username, password, etc)
            * commands settings

        """
        logger.debug('Init Config: {}'.format(kwargs))
        for k, v in kwargs.items():
            setattr(self, k, v)

    @property
    def server_url(self):
        server_cfg = getattr(self, 'server', {})
        return '{host}:{port}/{location}'.format(
            host=server_cfg['host'],
            port=server_cfg['port'],
            location=server_cfg['location'],
        )

    def get_monitoring_checks(self):
        """Get monitoring checks objects

        """
        logger.debug('Getting monitoring checks')
        monitoring_checks = [
            MonitoringCheck(getattr(self, 'hostname'), service_desc, cmd)
            for service_desc, cmd in getattr(self, 'commands').items()
        ]
        logger.debug(monitoring_checks)
        return monitoring_checks

    @staticmethod
    def get_default_hostname():
        """Get real FQDN

        :return:
        """
        return socket.getfqdn()

    def __unicode__(self):
        return u'Config({})'.format(getattr(self, 'server', None))


class ConfigReader(object):

    """Monitoring config reader"""

    @staticmethod
    def read_from_file(config_path, hostname):
        """ Read config from file

        :param config_path: path string to commands config
        :param hostname: string hostname
        """
        with open(config_path) as config_file:
            try:
                config = ConfigReader.read_from_string(
                    config_file.read(), hostname)
            except IOError as err:
                logger.error(
                    "Error read config '{}': {}".format(config_path, err))
            else:
                logger.info('Parsed config: {}'.format(config))
                return config
        return None

    @staticmethod
    def read_from_string(config_str, hostname):
        json_config = json.loads(config_str)
        json_config['hostname'] = hostname  # inject hostname
        return Config(**json_config)


class CheckManager(object):

    """ CheckManager. Manage MonitoringChecks """

    def __init__(self, monitoring_checks):
        """

        :param monitoring_checks: MonitoringCheck list
        """
        self.monitoring_checks = monitoring_checks

    def get_result(self):
        """Get monitoring check result for monitoring checks list

        :return: list of MonitoringCheckResult items
        """
        check_result_list = []
        for check in self.monitoring_checks:
            try:
                result = check.execute()
            except ForbiddenCheckError as err:
                logger.error(err)
            else:
                check_result_list.append(result)
        if check_result_list:
            return check_result_list
        else:
            logger.error("Empty check result list")


class MonitoringAgent(object):

    """Monitoring agent."""

    DEFAULT_HTTP_HEADERS = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    def __init__(self, config):
        self.config = config
        self.manager = CheckManager(config.get_monitoring_checks())

    def run(self):
        """ Run client.
        Steps:
            * Parse config file and get MonitoringCheck list
            * Execute each check and get dict result
            * Send request to monitoring server

        :return:
        """
        result_list = self.manager.get_result()  # [MonitoringCheckResult(), ]
        hostname = self.config.server['hostname']

        data = '&'.join(
            [check_result.get_url_encoded_string() for check_result in result_list] +
            [urlencode(dict(host_name=hostname, return_code=0, output='Host UP'))])

        logger.info("Sending request: {}".format(data))
        try:
            response = requests.post(
                self.config.server_url, data,
                headers=self.DEFAULT_HTTP_HEADERS,
                timeout=HTTP_TIMEOUT,
                auth=(self.config.server['username'],
                      self.config.server['password'])
            )
        except requests.RequestException as err:
            logger.error(err)
        else:
            logger.info("Request has been sent [{}]".format(
                response.status_code))
            return response


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-H', '--hostname', type=str,
                        help="Monitoring hostname")
    parser.add_argument('-C', '--config', type=str, help="Path to config")
    parser.add_argument('--log', type=str, help="Path to log")
    args = parser.parse_args()

    if args.config:
        setup_logging(args.log)
        hostname = getattr(args, 'hostname', Config.get_default_hostname())
        config = ConfigReader.read_from_file(args.config, hostname=hostname)
        agent = MonitoringAgent(config)
        agent.run()
    else:
        print("USAGE: python {} -H <host> -S <desc> -C <cmd> --log <path_to_log>"
              "".format(op.basename(__file__)))