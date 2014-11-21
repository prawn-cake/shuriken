# -*- coding: utf-8 -*-

import unittest

from shuriken.agent import (
    MonitoringCheck, ForbiddenCheckError, ConfigReader, Config,
    MonitoringCheckResult
)


class MonitoringCheckTestCase(unittest.TestCase):
    def test_stop_commands_check(self):
        allowed_commands = [
            '/usr/lib/nagios/plugins/check_swap -a -w50% -c10%',
            '/usr/lib/nagios/plugins/check_disk -w 10% -c 5% -p /'
        ]
        denied_commands = [
            'rm -rf /',
            'dd if=/dev/sda1 of=/dev/sda2',
            'rmdir /home',
            'cp -r /home /media/sdc1',
            'mv /home /tmp'
        ]
        for cmd in allowed_commands:
            self.assertTrue(MonitoringCheck.stop_commands_check(cmd))

        for cmd in denied_commands:
            self.assertRaises(
                ForbiddenCheckError, MonitoringCheck.stop_commands_check, cmd)

    def test_monitoring_check(self):
        params = dict(
            hostname='localhost',
            service='test_service',
            command='test command',
            is_mock=True
        )
        check = MonitoringCheck(**params)
        result = check.execute()
        self.assertIsInstance(result, MonitoringCheckResult)
        urlencoded_str = result.get_url_encoded_string()
        self.assertTrue(urlencoded_str)
        self.assertIsInstance(urlencoded_str, str)


class ConfigTestCase(unittest.TestCase):
    def test_config(self):
        raw_txt_config = """{
          "server": {
            "host": "http://monitoring.my_shinken_server.net",
            "port": 7760,
            "location": "push_check_result",
            "user": "",
            "password": ""
          },
          "plugins_dir": "/tmp",
          "commands": {
            "Disk/": "check_disk -w 10% -c 5% -p /",
            "Load": "check_load -w2.50,2.60,2.60 -c2.9,2.9,2.9",
            "Memory": "check_mem -f -w 10 -c 5",
            "Swap": "check_swap -a -w50% -c10%"
          }
        }
        """
        config = ConfigReader.read_from_string(raw_txt_config, 'localhost')
        self.assertIsInstance(config, Config)
        self.assertIsInstance(config.server, dict)
        self.assertIsInstance(config.commands, dict)
        self.assertTrue(config.plugins_dir)
        # check parameters
        self.assertEqual(config.server['port'], 7760)
        self.assertEqual(
            config.server_url,
            'http://monitoring.my_shinken_server.net:7760/push_check_result'
        )

        # test monitoring checks
        monitoring_checks = config.get_monitoring_checks()
        for check in monitoring_checks:
            self.assertIsInstance(check, MonitoringCheck)
            self.assertIn('/tmp/', check.command)