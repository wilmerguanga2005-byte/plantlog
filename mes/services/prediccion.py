"""Predicción de rendimiento final a partir de las primeras 4–6 h de telemetría.

Mock avanzado: el modelo (RandomForest) se entrena con corridas sintéticas calibradas con la receta.
Para producción, reemplazar `_dataset_sintetico()` por el histórico de lotes finalizados
(mismas 5 variables de entrada) y re-entrenar.
"""
from functools import lru_cache

import numpy as np
from django.utils import timezone
from datetime import timedelta

from ..models import LecturaProceso

DEFAULTS = {"TEMP": 27.0, "PH": 4.6, "BRIX": 10.0}


def _dataset_sintetico(n=600, seed=7):
    rng = np.random.default_rng(seed)
    temp, ph, brix = rng.normal(27, 1.6, n), rng.normal(4.6, 0.25, n), rng.normal(10, 1.5, n)
    pend, std = rng.normal(-0.35, 0.12, n), np.abs(rng.normal(0.6, 0.25, n))
    X = np.c_[temp, ph, brix, pend, std]
    # rendimiento relativo (fracción del teórico): penaliza desvío térmico, de pH y fermentación lenta
    y = 1 - 0.018 * np.abs(temp - 27) - 0.07 * np.abs(ph - 4.6) + 0.05 * (-pend - 0.35) - 0.02 * std + rng.normal(0, 0.008, n)
    return X, np.clip(y, 0.5, 1.02)


@lru_cache(maxsize=1)
def _modelo():
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.metrics import mean_absolute_error
    from sklearn.model_selection import train_test_split
    X, y = _dataset_sintetico()
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, random_state=1)
    m = RandomForestRegressor(n_estimators=80, random_state=1).fit(Xtr, ytr)
    return m, float(mean_absolute_error(yte, m.predict(Xte))) * 100  # MAE en puntos porcentuales


def _serie(lecturas, codigo):
    return [(l.timestamp, float(l.valor_medido)) for l in lecturas if l.variable.codigo == codigo]


def predecir_rendimiento(lote, horas=6):
    horas = max(4, min(int(horas), 6))
    desde = lote.fecha_inicio
    lecturas = list(LecturaProceso.objects.filter(lote=lote, timestamp__gte=desde, timestamp__lte=desde + timedelta(hours=horas))
                    .select_related("variable"))
    if len(lecturas) < 6:
        return {"disponible": False, "mensaje": "Se requieren al menos 6 lecturas dentro de las primeras 4–6 h del proceso."}
    t, p, b = (_serie(lecturas, c) for c in ("TEMP", "PH", "BRIX"))
    media = lambda s, c: float(np.mean([v for _, v in s])) if s else DEFAULTS[c]
    pendiente = 0.0
    if len(b) >= 3:
        x = [(ts - desde).total_seconds() / 3600 for ts, _ in b]
        pendiente = float(np.polyfit(x, [v for _, v in b], 1)[0])
    std_t = float(np.std([v for _, v in t])) if len(t) > 1 else 0.0
    feats = np.array([[media(t, "TEMP"), media(p, "PH"), media(b, "BRIX"), pendiente, std_t]])
    modelo, mae = _modelo()
    rel = float(modelo.predict(feats)[0])
    receta = lote.receta
    teorico = float(receta.rendimiento_teorico_pct)
    est = round(teorico * rel, 2)
    return {
        "disponible": True, "horas_analizadas": horas, "lecturas_usadas": len(lecturas),
        "rendimiento_estimado_pct": est, "rendimiento_teorico_pct": teorico,
        "mae_estimado_pct": round(mae * teorico / 100, 2),
        "volumen_proyectado": round(float(receta.tamano_corrida_base) * est / 100, 2),
        "unidad": receta.unidad_medida,
        "variables": {"temp_media": round(feats[0][0], 2), "ph_medio": round(feats[0][1], 2),
                      "brix_medio": round(feats[0][2], 2), "brix_pendiente_h": round(pendiente, 3)},
        "generado": timezone.now().isoformat(),
    }
