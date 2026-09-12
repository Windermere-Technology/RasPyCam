import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('camera_service', Path(__file__).resolve().parents[2] / 'etc/camera_service.py')
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)


class WatchdogTests(unittest.TestCase):
    @patch.object(service.time, 'sleep')
    @patch.object(service.os, 'kill')
    @patch.object(service, 'camera_processes', side_effect=[{123: 100}, {}])
    def test_term_is_sufficient_when_process_exits(self, processes, kill, sleep):
        service.stop_camera()
        kill.assert_called_once_with(123, service.signal.SIGTERM)

    @patch.object(service.time, 'monotonic', side_effect=[0, 31])
    @patch.object(service.os, 'kill')
    @patch.object(service, 'camera_processes', side_effect=[{123: 100}, {123: 200}])
    def test_reused_pid_is_not_killed(self, processes, kill, clock):
        service.stop_camera()
        kill.assert_called_once_with(123, service.signal.SIGTERM)

    @patch.object(service.time, 'monotonic', side_effect=[0, 31])
    @patch.object(service.os, 'kill')
    @patch.object(service, 'camera_processes', side_effect=[{123: 100}, {123: 100}, {}])
    def test_stuck_process_killed_only_after_deadline(self, processes, kill, clock):
        service.stop_camera()
        self.assertEqual([call.args[1] for call in kill.call_args_list],
                         [service.signal.SIGTERM, service.signal.SIGKILL])
