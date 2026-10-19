"""Public, read-only crypto analysis. Python 3 standard library only."""
import argparse
import concurrent.futures
import datetime as dt
import json
import math
from pathlib import Path
import time
import urllib.parse
import urllib.request

SPOT = 'https://data-api.binance.vision'
FUTURES = 'https://fapi.binance.com'
ALLOWED = {
    SPOT: {'/api/v3/time', '/api/v3/ticker/24hr', '/api/v3/klines'},
    FUTURES: {'/fapi/v1/time', '/fapi/v1/premiumIndex', '/fapi/v1/openInterest'},
}
SYMBOLS = ('BTCUSDT', 'ETHUSDT', 'SOLUSDT')
INTERVALS = {'1h': 3600000, '4h': 14400000, '1d': 86400000}


def get(base, path, **params):
    if path not in ALLOWED.get(base, set()):
        raise ValueError('Endpoint not explicitly allowlisted')
    url = base + path + ('?' + urllib.parse.urlencode(params) if params else '')
    req = urllib.request.Request(url, headers={'User-Agent': 'Cue-ReadOnly-Market-Analysis/1.0'}, method='GET')
    with urllib.request.urlopen(req, timeout=30) as response:
        result = json.load(response)
    if isinstance(result, dict) and 'code' in result:
        raise ValueError(str(result))
    return result


def ema(values, period):
    if not values:
        raise ValueError('Empty series')
    alpha = 2.0 / (period + 1)
    result = [float(values[0])]
    for value in values[1:]:
        result.append(alpha * value + (1 - alpha) * result[-1])
    return result


def wilder(values, period=14):
    if len(values) < period:
        raise ValueError('Insufficient smoothing history')
    value = sum(values[:period]) / period
    result = [value]
    for x in values[period:]:
        value = (value * (period - 1) + x) / period
        result.append(value)
    return result


def rsi(closes, period=14):
    changes = [b - a for a, b in zip(closes, closes[1:])]
    gains = wilder([max(x, 0) for x in changes], period)[-1]
    losses = wilder([max(-x, 0) for x in changes], period)[-1]
    if losses == 0:
        return 50.0 if gains == 0 else 100.0
    return 100 - 100 / (1 + gains / losses)


def macd(closes):
    fast, slow = ema(closes, 12), ema(closes, 26)
    line = [a - b for a, b in zip(fast, slow)]
    signal = ema(line, 9)
    return line, signal, [a - b for a, b in zip(line, signal)]


def closed_rows(rows, now, interval_ms):
    if not isinstance(rows, list):
        raise ValueError('Klines must be a list')
    result = [r for r in rows if int(r[6]) < now]
    if len(result) < 250:
        raise ValueError('Fewer than 250 closed bars')
    for i, row in enumerate(result):
        o, h, l, c, v = map(float, row[1:6])
        if not all(math.isfinite(x) for x in (o, h, l, c, v)) or min(o, h, l, c) <= 0 or v < 0:
            raise ValueError('Invalid price or volume')
        if h < max(o, c, l) or l > min(o, c, h):
            raise ValueError('Invalid OHLC ordering')
        if i and int(row[0]) - int(result[i - 1][0]) != interval_ms:
            raise ValueError('Missing, repeated or unordered candle')
    if not 0 <= now - int(result[-1][6]) <= interval_ms + 120000:
        raise ValueError('Stale candles')
    return result


def indicators(rows):
    closes = [float(r[4]) for r in rows]
    highs, lows = [float(r[2]) for r in rows], [float(r[3]) for r in rows]
    volumes = [float(r[5]) for r in rows]
    line, signal, histogram = macd(closes)
    tr = [max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1])) for i in range(1, len(rows))]
    atr = wilder(tr)[-1]
    mean = sum(closes[-20:]) / 20
    std = math.sqrt(sum((x - mean) ** 2 for x in closes[-20:]) / 20)
    e50, e200 = ema(closes, 50)[-1], ema(closes, 200)[-1]
    last = closes[-1]
    prior_volume = sum(volumes[-21:-1]) / 20
    return {
        'bars': len(rows), 'last_closed_utc': iso(int(rows[-1][6])), 'close': last,
        'ema50': e50, 'ema200': e200, 'rsi14_wilder': rsi(closes),
        'macd': line[-1], 'macd_signal': signal[-1], 'macd_histogram': histogram[-1],
        'macd_histogram_previous': histogram[-2], 'atr14_wilder': atr,
        'atr_percent': atr / last * 100,
        'bb20_lower': mean - 2 * std, 'bb20_middle': mean, 'bb20_upper': mean + 2 * std,
        'last_volume_to_previous20_mean': volumes[-1] / prior_volume if prior_volume else None,
        'range20_low': min(lows[-20:]), 'range20_high': max(highs[-20:]),
        'prior20_low': min(lows[-21:-1]), 'prior20_high': max(highs[-21:-1]),
        'trend': 'up' if last > e50 > e200 else 'down' if last < e50 < e200 else 'mixed',
    }


def iso(ms):
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).isoformat()


def position_size(equity, entry, stop, round_trip_fee_rate=0.001, slippage_rate=0.001):
    if equity <= 0 or entry <= 0 or stop <= 0 or entry == stop or round_trip_fee_rate < 0 or slippage_rate < 0:
        raise ValueError('Invalid risk inputs')
    risk = equity * 0.005
    cost_per_unit = abs(entry - stop) + entry * (round_trip_fee_rate + slippage_rate)
    return {'planned_risk_budget': risk, 'max_base_units_before_exchange_rounding': risk / cost_per_unit,
            'warning': 'Not an order. Actual losses can exceed planned risk due to gaps, slippage or liquidation.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    now = int(time.time() * 1000)
    server = get(SPOT, '/api/v3/time')
    if abs(server['serverTime'] - now) > 120000:
        raise ValueError('Local and exchange clocks differ by >120 seconds')
    snapshot = {'retrieved_utc': iso(now), 'exchange_utc': iso(server['serverTime']), 'market': 'Binance spot USDT; separate public USD-M futures context', 'assets': {}, 'errors': []}
    raw = {'time': server, 'spot': {}, 'futures': {}}
    tasks = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for symbol in SYMBOLS:
            tasks[pool.submit(get, SPOT, '/api/v3/ticker/24hr', symbol=symbol)] = (symbol, 'ticker', 'spot')
            for interval in INTERVALS:
                tasks[pool.submit(get, SPOT, '/api/v3/klines', symbol=symbol, interval=interval, limit=500)] = (symbol, interval, 'spot')
            for path, label in [('/fapi/v1/premiumIndex', 'premium'), ('/fapi/v1/openInterest', 'open_interest')]:
                tasks[pool.submit(get, FUTURES, path, symbol=symbol)] = (symbol, label, 'futures')
        for future in concurrent.futures.as_completed(tasks):
            symbol, label, market = tasks[future]
            try:
                raw[market].setdefault(symbol, {})[label] = future.result()
            except Exception as exc:
                snapshot['errors'].append(f'{symbol} {market} {label}: {exc}')
    for symbol in SYMBOLS:
        asset = {'timeframes': {}}
        data = raw['spot'].get(symbol, {})
        ticker = data.get('ticker')
        if ticker:
            if abs(now - int(ticker['closeTime'])) > 120000:
                snapshot['errors'].append(f'{symbol}: stale ticker, excluded')
            else:
                asset['ticker24h'] = {k: ticker[k] for k in ('lastPrice', 'priceChangePercent', 'highPrice', 'lowPrice', 'quoteVolume', 'closeTime')}
        for interval, duration in INTERVALS.items():
            try:
                asset['timeframes'][interval] = indicators(closed_rows(data[interval], now, duration))
            except Exception as exc:
                snapshot['errors'].append(f'{symbol} {interval}: {exc}')
        f = raw['futures'].get(symbol, {})
        asset['futures_public'] = {}
        for label, item in f.items():
            if 'time' not in item or abs(now - int(item['time'])) > 180000:
                snapshot['errors'].append(f'{symbol} {label}: stale or undated futures data, excluded')
            else:
                asset['futures_public'][label] = item
        snapshot['assets'][symbol] = asset
    (out / 'raw_market_data.json').write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding='utf-8')
    (out / 'market_analysis.json').write_text(json.dumps(snapshot, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(snapshot, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
