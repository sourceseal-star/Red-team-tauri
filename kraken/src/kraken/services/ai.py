import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.externals import joblib
from pathlib import Path
from datetime import datetime, timedelta
import threading
import time

from kraken.config.settings import settings
from kraken.core.database import db
from kraken.core.logger import logger

class AnomalyDetector:
    """Detector de anomalías usando Isolation Forest."""

    def __init__(self):
        self.model_path = Path(settings.ML_MODEL_PATH)
        self.scaler_path = self.model_path.parent / "scaler.pkl"
        self.model = None
        self.scaler = None
        self.last_training = None
        self.lock = threading.Lock()
        self._load_or_train_model()

    def _load_or_train_model(self):
        """Carga el modelo existente o entrena uno nuevo."""
        if self.model_path.exists() and self.scaler_path.exists():
            try:
                with self.lock:
                    self.model = joblib.load(self.model_path)
                    self.scaler = joblib.load(self.scaler_path)
                    self.last_training = datetime.fromtimestamp(self.model_path.stat().st_mtime)
                logger.info(f"✅ Modelo de IA cargado desde {self.model_path}")
            except Exception as e:
                logger.error(f"Error cargando modelo de IA: {e}")
                self.model = None
                self.scaler = None
        else:
            logger.info("🤖 Entrenando nuevo modelo de IA...")
            self._train_model()

    def _train_model(self):
        """Entrena el modelo de detección de anomalías."""
        # Obtener datos históricos
        data = self._get_training_data()
        if not data or len(data) < 10:
            logger.warning("⚠️ No hay suficientes datos para entrenar el modelo")
            return

        # Preparar características
        X = self._prepare_features(data)

        # Escalar características
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        # Entrenar modelo
        self.model = IsolationForest(
            n_estimators=100,
            max_samples='auto',
            contamination=0.1,  # Ajustar según datos
            random_state=42
        )
        self.model.fit(X_scaled)
        self.last_training = datetime.utcnow()

        # Guardar modelo
        try:
            with self.lock:
                self.model_path.parent.mkdir(parents=True, exist_ok=True)
                joblib.dump(self.model, self.model_path)
                joblib.dump(self.scaler, self.scaler_path)
            logger.info(f"✅ Modelo de IA entrenado y guardado en {self.model_path}")
        except Exception as e:
            logger.error(f"Error guardando modelo de IA: {e}")

    def _get_training_data(self) -> pd.DataFrame:
        """Obtiene datos históricos para entrenar el modelo."""
        session = db.get_session()
        try:
            # Obtener hosts con sus características
            query = session.query(
                HostDB.ip,
                HostDB.cvss_score,
                HostDB.total_vulns,
                HostDB.os,
                HostDB.last_seen
            ).filter(
                HostDB.last_seen >= datetime.utcnow() - timedelta(days=30)
            )

            data = []
            for row in query.all():
                data.append({
                    "ip": row.ip,
                    "cvss_score": row.cvss_score or 0,
                    "total_vulns": row.total_vulns or 0,
                    "is_windows": 1 if row.os and "windows" in row.os.lower() else 0,
                    "is_linux": 1 if row.os and "linux" in row.os.lower() else 0,
                    "days_since_seen": (datetime.utcnow() - row.last_seen).days if row.last_seen else 30
                })

            return pd.DataFrame(data)
        except Exception as e:
            logger.error(f"Error obteniendo datos para entrenamiento: {e}")
            return pd.DataFrame()
        finally:
            session.close()

    def _prepare_features(self, df: pd.DataFrame) -> np.ndarray:
        """Prepara las características para el modelo."""
        # Seleccionar características numéricas
        features = df[["cvss_score", "total_vulns", "is_windows", "is_linux", "days_since_seen"]].values
        return features

    def detect_anomalies(self, new_data: Dict) -> Dict:
        """Detecta anomalías en nuevos datos."""
        if self.model is None or self.scaler is None:
            self._load_or_train_model()
            if self.model is None:
                return {"is_anomaly": False, "anomaly_score": 0.0}

        # Preparar características
        features = np.array([[
            new_data.get("cvss_score", 0),
            new_data.get("total_vulns", 0),
            1 if new_data.get("os", "").lower().find("windows") >= 0 else 0,
            1 if new_data.get("os", "").lower().find("linux") >= 0 else 0,
            new_data.get("days_since_seen", 0)
        ]])

        # Escalar características
        features_scaled = self.scaler.transform(features)

        # Predecir
        is_anomaly = self.model.predict(features_scaled)[0] == -1
        anomaly_score = self.model.decision_function(features_scaled)[0]

        return {
            "is_anomaly": bool(is_anomaly),
            "anomaly_score": float(anomaly_score),
            "model_version": self.last_training.isoformat() if self.last_training else None
        }

    def check_and_train(self):
        """Verifica si es necesario reentrenar el modelo."""
        if not settings.ML_ENABLED:
            return

        # Reentrenar cada X horas
        if self.last_training:
            next_training = self.last_training + timedelta(seconds=settings.ML_TRAINING_INTERVAL)
            if datetime.utcnow() < next_training:
                return

        logger.info("🔄 Reentrenando modelo de IA...")
        self._train_model()

    def start_training_loop(self):
        """Inicia el bucle de reentrenamiento en segundo plano."""
        def loop():
            while True:
                try:
                    self.check_and_train()
                except Exception as e:
                    logger.error(f"Error en bucle de entrenamiento de IA: {e}")
                time.sleep(3600)  # Verificar cada hora

        thread = threading.Thread(target=loop, daemon=True)
        thread.start()
        return thread

# Singleton
anomaly_detector = AnomalyDetector()
