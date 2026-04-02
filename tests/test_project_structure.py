"""Tests for Story 1.1: Project structure and configuration."""

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TestPyprojectToml:
    """Verify pyproject.toml meets AC #1 and #3."""

    def setup_method(self):
        with open(ROOT / "pyproject.toml", "rb") as f:
            self.config = tomllib.load(f)

    def test_python_version_constraint(self):
        python_req = self.config["tool"]["poetry"]["dependencies"]["python"]
        assert ">=3.10" in python_req

    def test_mcp_dependency(self):
        deps = self.config["tool"]["poetry"]["dependencies"]
        assert "mcp" in deps
        assert ">=1.26.0" in deps["mcp"]

    def test_pydantic_settings_dependency(self):
        deps = self.config["tool"]["poetry"]["dependencies"]
        assert "pydantic-settings" in deps

    def test_pyyaml_dependency(self):
        deps = self.config["tool"]["poetry"]["dependencies"]
        assert "pyyaml" in deps

    def test_pytest_dev_dependency(self):
        dev_deps = self.config["tool"]["poetry"]["group"]["dev"]["dependencies"]
        assert "pytest" in dev_deps


class TestDirectoryStructure:
    """Verify directory structure meets AC #2."""

    def test_servers_imagen_exists(self):
        assert (ROOT / "servers" / "imagen").is_dir()

    def test_servers_imagen_init(self):
        assert (ROOT / "servers" / "imagen" / "__init__.py").is_file()

    def test_shared_exists(self):
        assert (ROOT / "shared").is_dir()

    def test_shared_init(self):
        assert (ROOT / "shared" / "__init__.py").is_file()

    def test_tests_exists(self):
        assert (ROOT / "tests").is_dir()

    def test_tests_conftest(self):
        assert (ROOT / "tests" / "conftest.py").is_file()

    def test_tests_imagen_exists(self):
        assert (ROOT / "tests" / "imagen").is_dir()

    def test_tests_shared_exists(self):
        assert (ROOT / "tests" / "shared").is_dir()

    def test_claude_skills_exists(self):
        assert (ROOT / ".claude" / "skills").is_dir()


class TestGitignore:
    """Verify .gitignore meets AC #4."""

    def setup_method(self):
        self.lines = (ROOT / ".gitignore").read_text().splitlines()

    def test_env_ignored(self):
        assert ".env" in self.lines

    def test_pycache_ignored(self):
        assert "__pycache__/" in self.lines

    def test_venv_ignored(self):
        assert ".venv/" in self.lines


class TestEnvExample:
    """Verify .env.example meets AC #5."""

    def setup_method(self):
        self.content = (ROOT / ".env.example").read_text()

    def test_gcp_project_listed(self):
        assert "IMAGEN_GCP_PROJECT=" in self.content

    def test_api_key_listed(self):
        assert "IMAGEN_API_KEY=" in self.content


class TestConfigYaml:
    """Verify config.yaml skeleton exists."""

    def test_config_yaml_exists(self):
        assert (ROOT / "config.yaml").is_file()

    def test_log_level_present(self):
        import yaml

        with open(ROOT / "config.yaml") as f:
            config = yaml.safe_load(f)
        assert config["log_level"] == "INFO"

    def test_imagen_section_present(self):
        import yaml

        with open(ROOT / "config.yaml") as f:
            config = yaml.safe_load(f)
        assert "imagen" in config
