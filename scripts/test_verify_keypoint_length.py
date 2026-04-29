"""T2026-0429-J: verify_keypoint_length.py の compute_distribution / classify をテスト。

ネットワーク I/O は mock せず、純粋関数のみテストする。
実行: python3 -m unittest scripts.test_verify_keypoint_length -v
"""
from __future__ import annotations

import importlib.util
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.abspath(__file__))
SPEC = importlib.util.spec_from_file_location(
    'verify_keypoint_length', os.path.join(ROOT, 'verify_keypoint_length.py')
)
mod = importlib.util.module_from_spec(SPEC)
sys.modules['verify_keypoint_length'] = mod
SPEC.loader.exec_module(mod)


class ComputeDistributionTest(unittest.TestCase):
    def test_empty(self):
        out = mod.compute_distribution([])
        self.assertEqual(out['total'], 0)

    def test_all_short(self):
        topics = [{'keyPoint': 'short text'} for _ in range(10)]
        out = mod.compute_distribution(topics)
        self.assertEqual(out['total'], 10)
        self.assertEqual(out['ge100'], 0)
        self.assertEqual(out['ge200'], 0)
        self.assertEqual(out['ge100_rate'], 0.0)

    def test_mixed(self):
        topics = [
            {'keyPoint': 'あ' * 50},
            {'keyPoint': 'あ' * 100},   # ge100
            {'keyPoint': 'あ' * 150},   # ge100
            {'keyPoint': 'あ' * 250},   # ge100, ge200
        ]
        out = mod.compute_distribution(topics)
        self.assertEqual(out['total'], 4)
        self.assertEqual(out['ge100'], 3)
        self.assertEqual(out['ge200'], 1)
        self.assertEqual(out['ge100_rate'], 75.0)
        self.assertEqual(out['ge200_rate'], 25.0)
        self.assertEqual(out['max_len'], 250)
        self.assertEqual(out['min_len'], 50)

    def test_handles_missing_keypoint(self):
        topics = [
            {'keyPoint': None},
            {},
            {'keyPoint': '  '},
            {'keyPoint': 'あ' * 200},
        ]
        out = mod.compute_distribution(topics)
        self.assertEqual(out['total'], 4)
        self.assertEqual(out['ge100'], 1)
        self.assertEqual(out['ge200'], 1)
        self.assertEqual(out['min_len'], 0)


class ClassifyTest(unittest.TestCase):
    def test_ok(self):
        self.assertEqual(mod.classify(70.0), 'ok')
        self.assertEqual(mod.classify(85.0), 'ok')

    def test_warn(self):
        self.assertEqual(mod.classify(69.99), 'warn')
        self.assertEqual(mod.classify(50.0), 'warn')

    def test_error(self):
        self.assertEqual(mod.classify(49.99), 'error')
        self.assertEqual(mod.classify(2.17), 'error')
        self.assertEqual(mod.classify(0.0), 'error')


if __name__ == '__main__':
    unittest.main(verbosity=2)
