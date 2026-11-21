"""Run every test:  python run_tests.py

No network, no touchpad and no screen access needed: fingers, Gemma, Sarvam and the
WhatsApp/Gmail steps are all faked, so this runs anywhere.
"""
import runpy
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

SUITES = ["test_gestures", "test_engine", "test_shapes", "test_agent", "test_writer"]

if __name__ == "__main__":
    for name in SUITES:
        print(f"\n== {name} ==")
        if name == "test_gestures":
            import tests.test_gestures as t
            t.test_all_shapes()
            t.test_scribble_rejected_or_any()
            print("ok shapes recognised, straight swipes ignored")
        else:
            runpy.run_path(os.path.join(HERE, "tests", f"{name}.py"), run_name="__main__")
    print("\nAll tests passed.")
