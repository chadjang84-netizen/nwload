import logging
import yaml
from ..models import Configuration, ThresholdConfig

logger = logging.getLogger(__name__)


class ConfigValidationError(Exception):
    pass


class ConfigParser:

    @staticmethod
    def parse(content: str) -> Configuration:
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            raise ConfigValidationError(f"YAML parse error: {e}")

        if not isinstance(data, dict):
            raise ConfigValidationError("Config must be a YAML mapping")

        thresholds = ConfigParser._parse_band_thresholds(data.get("thresholds", []))

        degraded_ratio = float(data.get("degraded_ratio", 0.25))
        step_up_ratio = float(data.get("step_up_ratio", 0.50))
        sliding_window = data.get("sliding_window_seconds", 300)
        recovery_cooldown = data.get("recovery_cooldown_seconds", 3600)
        step_up_interval = data.get("step_up_interval_seconds", 3600)
        supported_version = data.get("supported_version", 1)
        supported_message_type = data.get("supported_message_type", 1)
        max_onvif_retries = data.get("max_onvif_retries", 3)

        if recovery_cooldown <= 0:
            logger.warning("recovery_cooldown_seconds <= 0, using default 3600")
            recovery_cooldown = 3600

        return Configuration(
            thresholds=thresholds,
            degraded_ratio=degraded_ratio,
            step_up_ratio=step_up_ratio,
            sliding_window_seconds=sliding_window,
            recovery_cooldown_seconds=recovery_cooldown,
            step_up_interval_seconds=step_up_interval,
            supported_version=supported_version,
            supported_message_type=supported_message_type,
            max_onvif_retries=max_onvif_retries,
        )

    @staticmethod
    def _parse_single_threshold(data: dict) -> ThresholdConfig:
        return ThresholdConfig(
            warning=int(data["warning"]),
            congestion=int(data["congestion"]),
            overload_enter=int(data["overload_enter"]),
            overload_exit=int(data["overload_exit"]),
        )

    @staticmethod
    def _parse_band_thresholds(data) -> dict:
        # data: list of {band, warning, congestion, overload_enter, overload_exit}
        result = {}
        if not isinstance(data, list):
            return result
        for item in data:
            try:
                band = int(item["band"])
                result[band] = ConfigParser._parse_single_threshold(item)
            except (KeyError, ValueError, TypeError) as e:
                logger.warning("Skipping invalid band threshold entry: %s", e)
        return result

class ConfigPrinter:

    @staticmethod
    def print(config: Configuration) -> str:
        thresholds_list = [
            {
                "band": band,
                "warning": t.warning,
                "congestion": t.congestion,
                "overload_enter": t.overload_enter,
                "overload_exit": t.overload_exit,
            }
            for band, t in sorted(config.thresholds.items())
        ]

        data = {
            "thresholds": thresholds_list,
            "degraded_ratio": config.degraded_ratio,
            "step_up_ratio": config.step_up_ratio,
            "sliding_window_seconds": config.sliding_window_seconds,
            "recovery_cooldown_seconds": config.recovery_cooldown_seconds,
            "step_up_interval_seconds": config.step_up_interval_seconds,
            "supported_version": config.supported_version,
            "supported_message_type": config.supported_message_type,
            "max_onvif_retries": config.max_onvif_retries,
        }
        return yaml.dump(data, default_flow_style=False, allow_unicode=True)
