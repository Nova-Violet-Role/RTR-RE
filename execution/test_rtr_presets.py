# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""Shared retrieval CPU lattice plus RTR-RE context-preset tests.

Retrieval owns modality, per-model ONNX threads, and the parking budget.
RTR-RE composes that retrieval profile with its Compressor trigger,
Compressor target, and Keeper retained-message count. The axes stay
independent, and each host surface must name which composition it reads.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.absolute()))

from context_budget import (
    effective_threads_for_model,
    resolve_context_profile,
    resolve_retrieval_profile,
    symbiose_config,
)


class TestRetrievalProfile(unittest.TestCase):
    def test_retrieval_profile_carries_no_compressor_or_keeper_values(self):
        profile = resolve_retrieval_profile({})
        self.assertEqual(profile["modality"], "rtr-full")
        self.assertEqual(profile["threads_per_model"], 4)
        self.assertEqual(profile["parking_percent"], 60)
        self.assertEqual(profile["compute_preset"], "rtr-full/t4/p60")
        self.assertEqual(profile["profile_code"], "rtr-full/t4/p60")
        self.assertEqual(profile["profile_label"], "RTR-FULL · T4 · P60")
        for key in ("preset", "preset_display", "keeper"):
            self.assertNotIn(key, profile)

    def test_context_profile_is_the_rtrre_composition(self):
        profile = resolve_context_profile({})
        self.assertEqual(profile["preset"], "re-symbiose-mugen")
        self.assertEqual(profile["preset_display"], "Re-Symbiose-Mugen")
        self.assertEqual(profile["keeper"]["trigger_tokens"], 400000)
        self.assertEqual(profile["keeper"]["target_tokens"], 200000)
        self.assertEqual(profile["keeper"]["max_keep_messages"], 200)
        self.assertEqual(profile["modality"], "rtr-full")
        self.assertEqual(profile["threads_per_model"], 4)
        self.assertEqual(profile["parking_percent"], 60)
        self.assertEqual(profile["compute_preset"], "rtr-full/t4/p60")
        self.assertEqual(profile["profile_code"], "re-symbiose-mugen/rtr-full/t4/p60")
        self.assertEqual(
            profile["profile_label"], "Re-Symbiose-Mugen · RTR-FULL · T4 · P60"
        )

    def test_local_system_is_mugen_rtr_full_t8_p80(self):
        profile = resolve_context_profile(
            {"OPENCODE_MEMORY_RTR_PRESET_PROFILE": "local-system"}
        )
        self.assertEqual(profile["preset"], "re-symbiose-mugen")
        self.assertEqual(profile["threads_per_model"], 8)
        self.assertEqual(profile["parking_percent"], 80)
        self.assertEqual(profile["profile_code"], "re-symbiose-mugen/rtr-full/t8/p80")

    def test_legacy_profiles_are_aliases_not_parallel_defaults(self):
        balanced = resolve_retrieval_profile(
            {"OPENCODE_MEMORY_RTR_PROFILE": "balanced"}
        )
        performance = resolve_retrieval_profile(
            {"OPENCODE_MEMORY_RTR_PROFILE": "performance"}
        )
        self.assertEqual(balanced["cpu_profile"], "public-default")
        self.assertEqual(
            (balanced["threads_per_model"], balanced["parking_percent"]), (4, 60)
        )
        self.assertEqual(performance["cpu_profile"], "local-system")
        self.assertEqual(
            (performance["threads_per_model"], performance["parking_percent"]), (8, 80)
        )

    def test_three_ah_variants_use_decided_windows_and_same_cpu_default(self):
        expected = {
            "fusion-ah": (200000, 100000, 30, "Fusion-AH!"),
            "symbiose-ah": (250000, 100000, 40, "Symbiose-AH!"),
            "re-symbiose": (320000, 128000, 50, "Re-Symbiose"),
        }
        for name, (trigger, target, maximum, display) in expected.items():
            with self.subTest(name=name):
                cfg = symbiose_config({"OPENCODE_MEMORY_RTRRE_PRESET": name})
                self.assertEqual(cfg["preset"], name)
                self.assertEqual(cfg["preset_display"], display)
                self.assertEqual(cfg["trigger_tokens"], trigger)
                self.assertEqual(cfg["target_tokens"], target)
                self.assertEqual(cfg["max_keep_messages"], maximum)
                self.assertEqual(cfg["threads_per_model"], 4)
                self.assertEqual(cfg["parking_percent"], 60)

    def test_mugen_preset_resolves_with_exact_bounds_and_alias(self):
        cfg = symbiose_config({"OPENCODE_MEMORY_RTRRE_PRESET": "re-symbiose-mugen"})
        self.assertEqual(cfg["preset"], "re-symbiose-mugen")
        self.assertEqual(cfg["preset_display"], "Re-Symbiose-Mugen")
        self.assertEqual(cfg["trigger_tokens"], 400000)
        self.assertEqual(cfg["target_tokens"], 200000)
        self.assertEqual(cfg["max_keep_messages"], 200)
        alias_cfg = symbiose_config({"OPENCODE_MEMORY_RTRRE_PRESET": "mugen"})
        self.assertEqual(alias_cfg["preset"], "re-symbiose-mugen")
        self.assertEqual(alias_cfg["trigger_tokens"], 400000)
        default_cfg = symbiose_config({})
        self.assertEqual(default_cfg["preset"], "re-symbiose-mugen")
        self.assertEqual(default_cfg["trigger_tokens"], 400000)
        self.assertEqual(default_cfg["max_keep_messages"], 200)

    def test_modality_threads_and_parking_stay_independent(self):
        profile = resolve_retrieval_profile(
            {
                "OPENCODE_MEMORY_RETRIEVAL_MODALITY": "rag-dense-base",
                "OPENCODE_MEMORY_EMBED_THREADS": "12",
                "OPENCODE_MEMORY_CPU_PARKING_PERCENT": "30",
            }
        )
        self.assertEqual(profile["modality"], "rag-dense-base")
        self.assertEqual(profile["models"], ["BAAI/bge-base-en-v1.5"])
        self.assertFalse(profile["hybrid"])
        self.assertFalse(profile["expansion"])
        self.assertEqual(profile["threads_per_model"], 12)
        self.assertEqual(profile["parking_percent"], 30)
        self.assertEqual(profile["compute_preset"], "rag-dense-base/t12/p30")

    def test_invalid_cpu_choices_refuse_by_name(self):
        cases = [
            ("OPENCODE_MEMORY_EMBED_THREADS", "3", "OPENCODE_MEMORY_EMBED_THREADS"),
            (
                "OPENCODE_MEMORY_CPU_PARKING_PERCENT",
                "90",
                "OPENCODE_MEMORY_CPU_PARKING_PERCENT",
            ),
            (
                "OPENCODE_MEMORY_RETRIEVAL_MODALITY",
                "magic",
                "OPENCODE_MEMORY_RETRIEVAL_MODALITY",
            ),
            (
                "OPENCODE_MEMORY_RTR_PRESET_PROFILE",
                "mystery",
                "OPENCODE_MEMORY_RTR_PRESET_PROFILE",
            ),
        ]
        for env_name, value, named in cases:
            with self.subTest(env_name=env_name):
                with self.assertRaises(ValueError) as raised:
                    resolve_retrieval_profile({env_name: value})
                self.assertIn(named, str(raised.exception))

    def test_parking_arithmetic_bounds_every_loaded_model(self):
        self.assertEqual(
            effective_threads_for_model(16, 60, model_count=2, logical_processors=32),
            9,
        )
        self.assertEqual(
            effective_threads_for_model(8, 80, model_count=2, logical_processors=32),
            8,
        )
        self.assertEqual(
            effective_threads_for_model(4, 20, model_count=1, logical_processors=8),
            1,
        )


if __name__ == "__main__":
    unittest.main()
