import math
import warnings
from datetime import date, timedelta
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.arima.model import ARIMA
from xgboost import XGBRegressor
from sqlalchemy import select
from fastapi import HTTPException
from .models import Sale, StoredResult

def metrics(actual, predicted):
    a, p = np.asarray(actual, float), np.asarray(predicted, float)
    errors = a-p
    positive = a > 0
    return {'mae': float(np.mean(abs(errors))), 'rmse': float(np.sqrt(np.mean(errors**2))), 'mape': float(np.mean(abs(errors[positive]/a[positive]))*100) if positive.any() else None, 'wape': float(np.sum(abs(errors))/np.sum(a)*100) if np.sum(a) else None}

def features(history, index):
    return [*history[-7:], float(np.mean(history[-14:])), index, math.sin(2*math.pi*index/7), math.cos(2*math.pi*index/7)]

def predict(model, history, horizon):
    y = np.asarray(history, float)
    if model == 'Moving average':
        return np.repeat(np.mean(y[-14:]), horizon)
    if model == 'Exponential smoothing':
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            return np.maximum(0, ExponentialSmoothing(y, trend='add', seasonal='add' if len(y)>=28 else None, seasonal_periods=7).fit().forecast(horizon))
    if model == 'ARIMA':
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            return np.maximum(0, ARIMA(y, order=(2, 1, 1)).fit().forecast(horizon))
    X = [features(y[:i], i) for i in range(14, len(y))]
    reg = RandomForestRegressor(n_estimators=60, max_depth=6, random_state=42, n_jobs=1) if model == 'Random forest' else XGBRegressor(n_estimators=65, max_depth=3, learning_rate=.08, random_state=42, n_jobs=1)
    reg.fit(X, y[14:])
    values = list(y)
    for _ in range(horizon):
        values.append(max(0, float(reg.predict([features(values, len(values))])[0])))
    return np.array(values[-horizon:])

def forecast(db, product_id, horizon=30, persist=True):
    rows = db.scalars(select(Sale).where(Sale.product_id==product_id).order_by(Sale.date)).all()
    if len(rows) < 42:
        raise HTTPException(422, 'At least 42 daily observations are required. Import a complete daily series; missing dates are not assumed to mean zero sales.')
    start, end = date.fromisoformat(rows[0].date), date.fromisoformat(rows[-1].date)
    if (end-start).days+1 != len(rows):
        raise HTTPException(422, 'Sales history has missing daily observations. Fill missing dates explicitly before forecasting.')
    y = np.array([r.quantity for r in rows], float)
    hold = min(28, len(y)//5)
    train, valid, test = y[:-2*hold], y[-2*hold:-hold], y[-hold:]
    candidates = ['Moving average', 'Exponential smoothing']
    if len(train) >= 56:
        candidates += ['ARIMA', 'Random forest', 'XGBoost']
    comparison, failures = [], []
    for model in candidates:
        try:
            comparison.append({'model': model, **metrics(valid, predict(model, train, hold))})
        except Exception as exc:
            failures.append({'model': model, 'reason': type(exc).__name__})
    winner = min(comparison, key=lambda r:r['mae'])['model']
    test_pred = predict(winner, y[:-hold], hold)
    evaluation = metrics(test, test_pred)
    # Empirical held-out absolute residual quantile; descriptive, not guaranteed coverage.
    radius = float(np.quantile(abs(test-test_pred), .95))
    future = predict(winner, y, horizon)
    result = {'product_id': product_id, 'model': winner, 'horizon': horizon, 'validation': comparison, 'unavailable_models': failures, 'test_metrics': evaluation, 'split': {'train':len(train), 'validation':hold, 'test':hold}, 'interval_method':'95th percentile of held-out absolute errors; empirical, no coverage guarantee', 'history':[{'date':r.date,'actual':r.quantity} for r in rows[-60:]], 'test_predictions':[{'date':r.date,'actual':r.quantity,'predicted':round(float(p),2)} for r,p in zip(rows[-hold:],test_pred)], 'forecast':[{'date':(end+timedelta(days=i+1)).isoformat(),'predicted':round(float(p),2),'lower':round(max(0,float(p)-radius),2),'upper':round(float(p)+radius,2)} for i,p in enumerate(future)], 'total_demand':round(float(sum(future)),2), 'as_of':end.isoformat()}
    if persist:
        db.add(StoredResult(kind='forecast', product_id=product_id, data=result))
    return result
