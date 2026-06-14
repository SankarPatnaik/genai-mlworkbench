from typing import Dict, Any
from urllib.request import urlopen
from app.config import settings

try:
    import mlflow
except Exception:
    mlflow = None

class MLflowService:
    def __init__(self):
        if not mlflow:
            print("MLflow package is not installed. Run logging will use local fallback IDs.")
            return
        try:
            mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
            mlflow.set_experiment("GenAI_Workbench_Agents")
        except Exception as e:
            print(f"Failed to connect to MLflow: {e}. Logging runs in local fallback directory.")

    def log_run(self, params: Dict[str, Any], metrics: Dict[str, Any], tags: Dict[str, Any] = None) -> str:
        """
        Logs a single RAG or Agent generation turn to MLflow.
        Returns the MLflow Run ID.
        """
        run_id = "local_mock_run"
        if not mlflow:
            return run_id
        try:
            with mlflow.start_run() as run:
                run_id = run.info.run_id
                
                # Log general parameters
                mlflow.log_params(params)
                
                # Log operational metrics
                mlflow.log_metrics(metrics)
                
                # Log tags
                if tags:
                    mlflow.set_tags(tags)
                    
            return run_id
        except Exception as e:
            print(f"MLflow Run Logging failed: {e}")
            return run_id

    def get_run_url(self, run_id: str) -> str:
        """
        Gets direct URL link to MLflow tracking panel.
        """
        if run_id == "local_mock_run":
            return "#mlflow-local-not-running"
        return f"{settings.MLFLOW_TRACKING_URI}/#/experiments/0/runs/{run_id}"

    def is_available(self) -> bool:
        try:
            with urlopen(f"{settings.MLFLOW_TRACKING_URI}/health", timeout=2) as response:
                return response.status < 500
        except Exception:
            pass
        if not mlflow:
            return False
        try:
            mlflow.get_tracking_uri()
            mlflow.search_experiments(max_results=1)
            return True
        except Exception:
            return False

mlflow_service = MLflowService()
