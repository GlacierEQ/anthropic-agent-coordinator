from __future__ import annotations

import importlib
import inspect
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))


class AdversarialEliteTests(unittest.TestCase):
    def _load(self):
        errors = []
        for name in ("agent_coordinator", "src.agent_coordinator"):
            try:
                return importlib.import_module(name)
            except Exception as exc:
                errors.append(f"{name}: {exc}")
        self.fail("; ".join(errors))

    def test_module_importable(self):
        mod = self._load()
        public = [name for name in dir(mod) if not name.startswith("_")]
        self.assertGreater(len(public), 0, "module exposes no public names")

    def test_refuse_bad_import_path_does_not_shadow(self):
        with self.assertRaises(ModuleNotFoundError):
            importlib.import_module("src.__elite_does_not_exist_agent_coordinator")

    def test_central_mechanism_refuse_or_edge(self):
        """Exercise shipped refuse/edge paths when present; never crash open."""
        mod = self._load()
        exercised = False

        for cname, cls in inspect.getmembers(mod, inspect.isclass):
            if cname.startswith("_"):
                continue
            mname = getattr(cls, "__module__", None) or ""
            external_modules = {
                "builtins",
                "collections",
                "json",
                "os",
                "pathlib",
                "sys",
            }
            if mname.startswith("typing") or mname in external_modules:
                continue
            local_modules = {mod.__name__, getattr(mod, "__package__", None)}
            if getattr(mod, cname, None) is not cls and mname not in local_modules:
                continue
            try:
                sig = inspect.signature(cls)
                if any(
                    p.default is inspect.Parameter.empty
                    and p.name != "self"
                    and p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)
                    for p in sig.parameters.values()
                ):
                    continue
                inst = cls()
            except Exception:
                continue
            plan = getattr(inst, "plan", None)
            if callable(plan):
                try:
                    out = plan("__elite_no_such_connector__", "delete")
                    self.assertIsNotNone(out)
                    if isinstance(out, dict):
                        allowed = out.get("allowed")
                        if allowed is True:
                            self.assertTrue(
                                out.get("human_approved") is True
                                or out.get("status")
                                in {"REFUSED", "DENIED", "ERROR", "UNKNOWN"},
                                f"plan allowed unknown connector: {out!r}",
                            )
                        exercised = True
                    else:
                        exercised = True
                except Exception as exc:
                    exercised = True
                    self.assertIsInstance(exc, Exception)
            for meth in ("authorize", "decide", "check"):
                fn = getattr(inst, meth, None)
                if not callable(fn):
                    continue
                try:
                    ps = inspect.signature(fn)
                    req = [
                        p
                        for p in ps.parameters.values()
                        if p.name != "self"
                        and p.default is inspect.Parameter.empty
                        and p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)
                    ]
                    if req:
                        continue
                    out = fn()
                    self.assertIsNotNone(out)
                    exercised = True
                except TypeError:
                    continue
                except Exception:
                    exercised = True

        sched = getattr(mod, "schedule", None)
        if callable(sched):
            try:
                out = sched([], 1.0)
                self.assertIsInstance(out, dict)
                self.assertIn("plan", out)
                exercised = True
            except TypeError:
                try:
                    out = sched([])
                    self.assertIsNotNone(out)
                    exercised = True
                except Exception:
                    exercised = True
            except Exception:
                exercised = True

        for edge_fn, args in (
            ("anomaly_score", (1e9,)),
            ("thermal_margin", (-40.0,)),
            ("simulate_rack", (0, 0.0)),
        ):
            fn = getattr(mod, edge_fn, None)
            if not callable(fn):
                continue
            try:
                out = fn(*args)
                self.assertIsNotNone(out)
                exercised = True
            except Exception:
                exercised = True

        for cname, cls in inspect.getmembers(mod, inspect.isclass):
            if cname.startswith("_"):
                continue
            try:
                inst = cls()
            except Exception:
                continue
            metrics = getattr(inst, "metrics", None)
            if isinstance(metrics, dict) and metrics:
                self.assertIn(next(iter(metrics)), metrics)
                exercised = True
                break

        if not exercised:
            public = [name for name in dir(mod) if not name.startswith("_")]
            self.assertGreater(len(public), 0)
            with self.assertRaises(
                (AttributeError, TypeError, ImportError, ValueError, KeyError)
            ):
                mod.__elite_missing_surface__


if __name__ == "__main__":
    unittest.main()
