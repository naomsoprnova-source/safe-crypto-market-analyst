"""Deterministic unit tests; fixtures are for testing, never market analysis."""
import math
import unittest
from analyze_market import ema, macd, rsi, wilder, closed_rows, position_size, get, SPOT, indicators

class IndicatorTests(unittest.TestCase):
    def test_ema_known(self):
        self.assertEqual(ema([1, 2, 3], 3), [1.0, 1.5, 2.25])

    def test_macd_against_independent_weighted_formula(self):
        prices = [100 + i * 0.1 + math.sin(i / 4) * 3 for i in range(100)]
        def direct(x, p):
            a = 2 / (p + 1)
            return [x[0] * (1-a)**n + sum(a*x[k]*(1-a)**(n-k) for k in range(1,n+1)) for n in range(len(x))]
        line, signal, hist = macd(prices)
        ref_line = [x-y for x,y in zip(direct(prices,12),direct(prices,26))]
        ref_signal = direct(ref_line,9)
        for a,b in zip(line, ref_line): self.assertAlmostEqual(a,b,places=10)
        for a,b in zip(signal, ref_signal): self.assertAlmostEqual(a,b,places=10)
        for a,b,c in zip(line, signal, hist): self.assertAlmostEqual(c,a-b,places=12)
        self.assertGreater(max(abs(x) for x in hist), 0.01)

    def test_rsi_edges(self):
        self.assertEqual(rsi([10.0]*30), 50)
        self.assertEqual(rsi(list(range(1,31))),100)
        self.assertEqual(rsi(list(range(30,0,-1))),0)
        with self.assertRaises(ValueError): rsi([1,2])

    def test_wilder_seed_and_update(self):
        self.assertEqual(wilder([1,2,3,8],3),[2.0,4.0])
        closes = [100]
        for x in [1,-1]*7 + [2]: closes.append(closes[-1]+x)
        gain = (0.5*13+2)/14
        loss = (0.5*13)/14
        self.assertAlmostEqual(rsi(closes), 100-100/(1+gain/loss))

    def test_atr_gap(self):
        rows = []
        for i in range(30):
            c = 100 if i < 29 else 110
            rows.append([i*1000,c,c+1,c-1,c,10,i*1000+999])
        result = indicators(rows)
        self.assertAlmostEqual(result['atr14_wilder'], (2*13+11)/14)

    def test_unclosed_missing_stale_rejected(self):
        rows = [[i*1000,10,11,9,10,2,i*1000+999] for i in range(301)]
        self.assertEqual(len(closed_rows(rows,300500,1000)),300)
        with self.assertRaises(ValueError): closed_rows(rows[:100]+rows[101:],300500,1000)
        with self.assertRaises(ValueError): closed_rows(rows,999999,1000)
        with self.assertRaises(ValueError): closed_rows(rows[:10],300500,1000)

    def test_planned_risk_cap(self):
        x=position_size(1000,100,98,0.001,0.001)
        self.assertEqual(x['planned_risk_budget'],5)
        self.assertLessEqual(x['max_base_units_before_exchange_rounding']*2.2,5.000000001)
        with self.assertRaises(ValueError): position_size(1000,100,100)

    def test_no_order_endpoint(self):
        with self.assertRaises(ValueError): get(SPOT,'/api/v3/order')

if __name__ == '__main__': unittest.main(verbosity=2)
