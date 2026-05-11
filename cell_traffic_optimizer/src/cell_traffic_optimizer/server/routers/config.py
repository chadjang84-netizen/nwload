from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from ..deps import get_state
from ..state import AppState, save_config_yaml
from ..schemas import ConfigurationSchema, DegradationConfigSchema, BandThresholdSchema
from ...models import ThresholdConfig, Configuration
from ...config import ConfigPrinter

router = APIRouter(prefix="/api/config", tags=["config"])


def _to_schema(config: Configuration) -> ConfigurationSchema:
    thresholds = [
        BandThresholdSchema(
            band=band,
            warning=t.warning,
            congestion=t.congestion,
            overloadEnter=t.overload_enter,
            overloadExit=t.overload_exit,
        )
        for band, t in sorted(config.thresholds.items())
    ]
    return ConfigurationSchema(
        thresholds=thresholds,
        degradation=DegradationConfigSchema(
            degradedRatio=config.degraded_ratio,
            stepUpRatio=config.step_up_ratio,
        ),
        slidingWindowSeconds=config.sliding_window_seconds,
        recoveryCooldownSeconds=config.recovery_cooldown_seconds,
        stepUpIntervalSeconds=config.step_up_interval_seconds,
        maxOnvifRetries=config.max_onvif_retries,
    )


@router.get("", response_model=ConfigurationSchema)
def get_config(state: AppState = Depends(get_state)):
    return _to_schema(state.config)


@router.post("", response_model=ConfigurationSchema)
def save_config(body: ConfigurationSchema, state: AppState = Depends(get_state)):
    thresholds = {}
    seen_bands = set()
    for item in body.thresholds:
        if item.band in seen_bands:
            raise HTTPException(status_code=422, detail=f"Duplicate band: {item.band}")
        seen_bands.add(item.band)
        try:
            thresholds[item.band] = ThresholdConfig(
                warning=item.warning,
                congestion=item.congestion,
                overload_enter=item.overloadEnter,
                overload_exit=item.overloadExit,
            )
        except ValueError as e:
            raise HTTPException(status_code=422, detail=f"Band {item.band}: {e}")

    if not thresholds:
        raise HTTPException(status_code=422, detail="At least one band threshold is required")

    degraded_ratio = body.degradation.degradedRatio
    step_up_ratio = body.degradation.stepUpRatio
    if not (0 < degraded_ratio < 1):
        raise HTTPException(status_code=422, detail="degradedRatio must be between 0 and 1")
    if not (0 < step_up_ratio < 1):
        raise HTTPException(status_code=422, detail="stepUpRatio must be between 0 and 1")
    if degraded_ratio >= step_up_ratio:
        raise HTTPException(status_code=422, detail="degradedRatio must be less than stepUpRatio")

    state.config = Configuration(
        thresholds=thresholds,
        degraded_ratio=degraded_ratio,
        step_up_ratio=step_up_ratio,
        sliding_window_seconds=body.slidingWindowSeconds,
        recovery_cooldown_seconds=body.recoveryCooldownSeconds,
        step_up_interval_seconds=body.stepUpIntervalSeconds,
        max_onvif_retries=body.maxOnvifRetries,
    )
    state.config_yaml = ConfigPrinter.print(state.config)
    save_config_yaml(state.config_yaml)
    state.rebuild_pipeline()
    return _to_schema(state.config)
