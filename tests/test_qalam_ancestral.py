"""
Tests unitarios para el módulo Qalam Ancestral (/api/qalam).
"""

import json
from datetime import datetime, timezone, timedelta
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from redteam.modules import qalam_ancestral


@pytest.fixture
def env(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    model_file = data_dir / "qalam_model.json"
    journal_file = data_dir / "qalam_journal.jsonl"
    zsh_file = tmp_path / ".zsh_history"
    bash_file = tmp_path / ".bash_history"

    monkeypatch.setattr(qalam_ancestral, "DATA_DIR", data_dir)
    monkeypatch.setattr(qalam_ancestral, "MODEL_FILE", model_file)
    monkeypatch.setattr(qalam_ancestral, "JOURNAL_FILE", journal_file)
    monkeypatch.setattr(qalam_ancestral, "ZSH_HISTORY_FILE", zsh_file)
    monkeypatch.setattr(qalam_ancestral, "BASH_HISTORY_FILE", bash_file)

    app = FastAPI()
    app.include_router(qalam_ancestral.router)
    client = TestClient(app)

    return {
        "client": client,
        "tmp_path": tmp_path,
        "zsh_file": zsh_file,
        "bash_file": bash_file,
        "model_file": model_file,
        "journal_file": journal_file,
    }


def test_explicit_train_vs_no_auto_train(env):
    client = env["client"]
    model_file = env["model_file"]
    zsh_file = env["zsh_file"]

    # 1. Prediction without model -> returns empty, does NOT auto train
    res = client.post("/api/qalam/predecir", json={"texto": "git"})
    assert res.status_code == 200
    data = res.json()
    assert data["sugerencias"] == []
    assert data["estado_modelo"] == "no_entrenado"
    assert not model_file.exists()

    # 2. Add history and explicitly train
    zsh_file.write_text("git status\ngit status\ngit commit -m\n", encoding="utf-8")
    res_train = client.post("/api/qalam/entrenar", json={})
    assert res_train.status_code == 200
    assert res_train.json()["status"] == "ok"
    assert model_file.exists()

    # 3. Prediction after explicit training
    res_pred = client.post("/api/qalam/predecir", json={"texto": "git"})
    assert res_pred.status_code == 200
    data_pred = res_pred.json()
    assert data_pred["estado_modelo"] == "entrenado"
    assert len(data_pred["sugerencias"]) > 0
    assert any("git status" in s for s in data_pred["sugerencias"])


def test_zsh_and_bash_history_fallback(env):
    client = env["client"]
    zsh_file = env["zsh_file"]
    bash_file = env["bash_file"]

    # Test ZSH preference when ZSH exists
    zsh_file.write_text("git diff\n", encoding="utf-8")
    bash_file.write_text("docker ps\n", encoding="utf-8")

    res = client.post("/api/qalam/entrenar", json={})
    assert res.status_code == 200
    assert res.json()["fuente_usada"] == "zsh_history"

    # Test BASH fallback when ZSH does not exist
    zsh_file.unlink()
    res2 = client.post("/api/qalam/entrenar", json={})
    assert res2.status_code == 200
    assert res2.json()["fuente_usada"] == "bash_history"


def test_secrets_not_persisted_or_returned(env):
    client = env["client"]
    zsh_file = env["zsh_file"]
    model_file = env["model_file"]

    sensitive_history = (
        "export AWS_SECRET_ACCESS_KEY=AKIAIOSFODNN7EXAMPLE1234\n"
        "curl -H 'Authorization: Bearer secret_token_xyz987' https://api.test.com\n"
        "git commit -m 'added password=super_secret_pass_123'\n"
        "echo API_KEY=x8f9a2b1c3d4e5f6g7h8i9j0k\n"
        ": 1690000000:0;git status\n"
        ": 1690000001:0;git commit -m\n"
    )
    zsh_file.write_text(sensitive_history, encoding="utf-8")

    # Train
    res = client.post("/api/qalam/entrenar", json={})
    assert res.status_code == 200

    # Read raw model content
    model_text = model_file.read_text(encoding="utf-8")
    assert "AKIAIOSFODNN7EXAMPLE1234" not in model_text
    assert "secret_token_xyz987" not in model_text
    assert "super_secret_pass_123" not in model_text
    assert "x8f9a2b1c3d4e5f6g7h8i9j0k" not in model_text

    # Verify prediction outputs contain no secrets
    res_pred = client.post("/api/qalam/predecir", json={"texto": "git"})
    pred_str = json.dumps(res_pred.json())
    assert "super_secret_pass_123" not in pred_str
    assert "AKIA" not in pred_str

    # Verify eco output contains no raw history
    res_eco = client.get("/api/qalam/eco")
    eco_str = json.dumps(res_eco.json())
    assert "AKIA" not in eco_str
    assert "super_secret_pass_123" not in eco_str


def test_invalid_inputs(env):
    client = env["client"]

    # Input exceeding max_length=256
    long_text = "a" * 300
    res = client.post("/api/qalam/predecir", json={"texto": long_text})
    assert res.status_code == 422  # Pydantic validation error

    # Invalid JSON payload
    res_invalid = client.post(
        "/api/qalam/predecir",
        headers={"Content-Type": "application/json"},
        content="invalid json"
    )
    assert res_invalid.status_code == 422


def test_actual_24h_filtering_in_eco(env):
    client = env["client"]
    journal_file = env["journal_file"]

    now = datetime.now(timezone.utc)
    old_ts = (now - timedelta(hours=30)).isoformat()
    recent_ts = (now - timedelta(hours=2)).isoformat()

    old_record = {
        "timestamp": old_ts,
        "event": "entrenamiento",
        "categoria": "comando",
        "detalles": {"test": "old"}
    }
    recent_record = {
        "timestamp": recent_ts,
        "event": "prediccion",
        "categoria": "comando",
        "detalles": {"test": "recent"}
    }

    journal_file.write_text(
        json.dumps(old_record) + "\n" + json.dumps(recent_record) + "\n",
        encoding="utf-8"
    )

    res = client.get("/api/qalam/eco")
    assert res.status_code == 200
    data = res.json()

    # Old record (30h) must be filtered out; only recent record (2h) included
    assert data["eventos_totales_24h"] == 1
    assert data["predicciones_24h"] == 1
    assert data["entrenamientos_24h"] == 0
    assert data["fuentes"] == []
    assert data["available"] == []
    assert data["sello_claims"] is None


def test_corrupt_model_honest_recoverable_response(env):
    client = env["client"]
    model_file = env["model_file"]
    zsh_file = env["zsh_file"]

    # Corrupt model file
    model_file.write_text("CORRUPTED_JSON_DATA{{{", encoding="utf-8")

    # Check estado
    res_est = client.get("/api/qalam/estado")
    assert res_est.status_code == 200
    assert res_est.json()["estado_modelo"] == "modelo_corrupto"
    assert res_est.json()["entrenado"] is False

    # Check prediction handles corrupt model gracefully without 500 error
    res_pred = client.post("/api/qalam/predecir", json={"texto": "git"})
    assert res_pred.status_code == 200
    assert res_pred.json()["sugerencias"] == []
    assert res_pred.json()["estado_modelo"] == "modelo_corrupto"

    # Retrain and recover
    zsh_file.write_text("git status\n", encoding="utf-8")
    res_train = client.post("/api/qalam/entrenar", json={})
    assert res_train.status_code == 200
    assert res_train.json()["status"] == "ok"

    # Verify recovered state
    res_est_recovered = client.get("/api/qalam/estado")
    assert res_est_recovered.json()["estado_modelo"] == "listo"
    assert res_est_recovered.json()["entrenado"] is True


def test_missing_history_file(env):
    client = env["client"]

    # No history: honest error and no empty replacement model.
    res = client.post("/api/qalam/entrenar", json={})
    assert res.status_code == 409
    assert not env["model_file"].exists()


def test_valid_json_but_unsafe_model_is_rejected(env):
    env["model_file"].write_text(json.dumps({"top_bigrams": [["git", "private-value"]]}))
    result = env["client"].post("/api/qalam/predecir", json={"texto": "git"})
    assert result.json()["estado_modelo"] == "modelo_corrupto"
    assert "private-value" not in result.text


def test_private_bounded_journal_and_sensitive_prediction(env):
    env["zsh_file"].write_text("git status\n")
    env["client"].post("/api/qalam/entrenar", json={})
    result = env["client"].post("/api/qalam/predecir", json={"texto": "secret=abc"})
    assert result.json()["sugerencias"] == []
    assert env["model_file"].stat().st_mode & 0o777 == 0o600
    assert env["journal_file"].stat().st_mode & 0o777 == 0o600
    assert "secret=abc" not in env["journal_file"].read_text()


def test_missing_history_preserves_existing_model(env):
    env["model_file"].write_text('{"top_bigrams": [["git", "status"]]}')
    original = env["model_file"].read_text()
    assert env["client"].post("/api/qalam/entrenar", json={}).status_code == 409
    assert env["model_file"].read_text() == original


def test_journal_retention_limit(env, monkeypatch):
    monkeypatch.setattr(qalam_ancestral, "MAX_JOURNAL_EVENTS", 3)
    for _ in range(5):
        qalam_ancestral.append_journal_event("prediccion", {"sugerencias_count": 1})
    assert len(env["journal_file"].read_text().splitlines()) == 3
