"""Isolamento da suíte offline.

O catálogo versionado `src/catalog/zh_identity.json` é dado real e muda a cada regeneração;
os testes do crivo chinês não podem depender do que ele diz hoje sobre uma URL de exemplo.
Por padrão nenhum teste vê catálogo (regra por set vale sozinha); quem precisa injeta o
seu com `monkeypatch.setattr(cs.zh_identity, "load", ...)`, como `tests/test_zh_identity.py`."""
import pytest

from src import zh_identity


@pytest.fixture(autouse=True)
def _no_real_zh_catalog(monkeypatch):
    monkeypatch.setattr(zh_identity, "load", lambda path=zh_identity.CATALOG_PATH: None)
    yield
