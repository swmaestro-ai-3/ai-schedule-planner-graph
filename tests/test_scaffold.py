import importlib
import json
import py_compile
from pathlib import Path


def test_planner_package_imports():
    planner = importlib.import_module("planner")

    assert planner.__name__ == "planner"


def test_streamlit_entrypoint_compiles():
    app_path = Path(__file__).resolve().parents[1] / "app.py"

    py_compile.compile(str(app_path), doraise=True)


def test_node_manifest_declares_openai_oauth_dependency():
    package_path = Path(__file__).resolve().parents[1] / "package.json"
    package_data = json.loads(package_path.read_text())

    assert package_data["dependencies"]["openai-oauth"] == "1.0.2"
