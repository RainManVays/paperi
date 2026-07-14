from pathlib import Path

from periprint.infra.config_store import AppConfig, ConfigStore


def test_load_returns_defaults_when_missing(tmp_path: Path) -> None:
    store = ConfigStore(path=tmp_path / "config.json")

    config = store.load()

    assert config == AppConfig()


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    store = ConfigStore(path=tmp_path / "config.json")
    config = AppConfig(
        active_printer_id="abc-123",
        auto_connect_on_start=False,
        default_chunk_height_px=150,
        theme="light",
        log_level="DEBUG",
    )

    store.save(config)
    reloaded = store.load()

    assert reloaded == config
