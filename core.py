# -*- coding: utf-8 -*-
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple, Dict
import pandas as pd
import math
import random

STEP_UNITS = 10
BOUNDS_MIN_FACTOR = 0.5
BOUNDS_MAX_FACTOR = 1.7

@dataclass
class Inputs:
    start_date: pd.Timestamp
    end_date: pd.Timestamp

    B2_STOT: float
    C2_SPREV: float
    D2_SCUR: float
    E2_START_BAL: float

    B3_ETOT: float
    C3_EPREV: float
    D3_ECUR: float
    E3_END_BAL: float

    topup1_net: float
    topup2_net: float

    p1: float
    p2: float
    p3: float
    stamp: float  # fixed 0.036
    monthly_fee: float
    zero_tail: int

def tiers_from_p1(p1: float) -> Tuple[float, float]:
    p1r = round(p1,2)
    mapping = {
        2.35: (3.1, 3.6),
        2.50: (3.25, 3.75),
        2.60: (3.35, 4.00),
        3.00: (4.00, 5.00),
        4.00: (5.00, 7.00),
    }
    if p1r in mapping:
        return mapping[p1r]
    p2 = p1 + 0.75
    p3 = p2 + 0.5
    return (p2, p3)

def price_no_fee(q: float, p1: float, p2: float, p3: float, stamp: float) -> float:
    t1, t2, t3 = p1+stamp, p2+stamp, p3+stamp
    if q <= 30.0:
        return q*t1
    elif q <= 60.0:
        return 30.0*t1 + (q-30.0)*t2
    else:
        return 30.0*t1 + 30.0*t2 + (q-60.0)*t3

def months_between(start_date: pd.Timestamp, end_date: pd.Timestamp) -> List[pd.Timestamp]:
    sMon = pd.Timestamp(year=start_date.year, month=start_date.month, day=1)
    eMon = pd.Timestamp(year=end_date.year, month=end_date.month, day=1)
    ePrev = eMon - pd.offsets.MonthBegin(1)
    total_months = (ePrev.year - sMon.year)*12 + (ePrev.month - sMon.month) + 1
    total_months = max(1, total_months)
    months = []
    cur = sMon
    for _ in range(total_months):
        months.append(cur)
        cur = cur + pd.offsets.MonthBegin(1)
    return months

def to_units(q: float) -> int:
    return int(round(q*STEP_UNITS))

def from_units(u: int) -> float:
    return u/STEP_UNITS

def distribute(inp: Inputs):
    p2_calc, p3_calc = tiers_from_p1(inp.p1)
    p2 = inp.p2 if inp.p2>0 else p2_calc
    p3 = inp.p3 if inp.p3>0 else p3_calc

    F6  = round(inp.E2_START_BAL + inp.topup1_net + inp.topup2_net, 3)
    F10 = price_no_fee(inp.D2_SCUR, inp.p1, p2, p3, inp.stamp)
    F11 = price_no_fee(inp.D3_ECUR, inp.p1, p2, p3, inp.stamp)

    q_target = max(0.0, round(inp.B3_ETOT - inp.D3_ECUR - inp.B2_STOT + inp.D2_SCUR, 1))
    v_target = max(0.0, round((F6 + F10) - (inp.E3_END_BAL + F11), 3))

    months = months_between(inp.start_date, inp.end_date)
    m = len(months)

    d2 = inp.D2_SCUR
    c3 = inp.C3_EPREV

    minU = [0]*m
    maxU = [0]*m
    fixed = [False]*m
    qU = [0]*m

    for idx in range(m):
        if idx == 0:
            mn = max(d2, c3*BOUNDS_MIN_FACTOR)
            mx = max(mn, c3*BOUNDS_MAX_FACTOR)
        elif idx == m-1:
            mn = mx = c3
            fixed[idx] = True
            qU[idx] = to_units(c3)
        else:
            mn = c3*BOUNDS_MIN_FACTOR
            mx = max(mn, c3*BOUNDS_MAX_FACTOR)
        mn = max(0.0, mn)
        minU[idx] = to_units(mn)
        maxU[idx] = to_units(mx)

    zero_tail = int(max(0, min(inp.zero_tail, m-1)))
    if zero_tail>0:
        for idx in range(m - zero_tail - 1, m-1):
            minU[idx] = maxU[idx] = 0
            qU[idx] = 0
            fixed[idx] = True

    totalU = to_units(q_target)
    sumMin = sum(minU)
    if sumMin > totalU and sumMin>0:
        scale = totalU/sumMin
        for i in range(m):
            if not fixed[i]:
                minU[i] = int(minU[i]*scale)
                if minU[i] > maxU[i]:
                    minU[i] = maxU[i]

    qU = minU[:]
    capacity = [max(0, maxU[i]-qU[i]) for i in range(m)]
    left = totalU - sum(qU)
    if left>0:
        weights = [cap*(1.0 + 0.12) for cap in capacity]
        s = sum(weights)
        if s>0:
            for i in range(m):
                add = int(left*(weights[i]/s))
                qU[i] = min(maxU[i], qU[i]+add)
            remain = totalU - sum(qU)
            j = 0
            while remain>0 and j<100000:
                idx = j % m
                if qU[idx] < maxU[idx] and not fixed[idx]:
                    qU[idx]+=1; remain-=1
                j+=1

    def price_tbl_value(u: int) -> int:
        return int(round(price_no_fee(from_units(u), inp.p1, p2, p3, inp.stamp)*1000))

    vM_noFee = [price_tbl_value(u) for u in qU]

    feeM = int(round(inp.monthly_fee*1000))
    targetTotalM = int(round(v_target*1000))
    targetNoFeeM = max(0, targetTotalM - feeM*m)

    def try_move(i,j):
        if i==j: return False
        if qU[i]+1>maxU[i] or qU[j]-1<minU[j]: return False
        before = vM_noFee[i] + vM_noFee[j]
        after = price_tbl_value(qU[i]+1) + price_tbl_value(qU[j]-1)
        cur = sum(vM_noFee)
        need = targetNoFeeM - cur
        delta = after - before
        if abs(need - delta) < abs(need):
            qU[i]+=1; qU[j]-=1
            vM_noFee[i]=price_tbl_value(qU[i])
            vM_noFee[j]=price_tbl_value(qU[j])
            return True
        return False

    for _ in range(3000):
        cur = sum(vM_noFee)
        need = targetNoFeeM - cur
        if need==0: break
        i = random.randrange(m); j=random.randrange(m)
        try_move(i,j)

    vDispM = [vM_noFee[i] + feeM for i in range(m)]
    sM = sum(vDispM)
    diffM = targetTotalM - sM
    i = m-1 if m>0 else 0
    while diffM!=0 and m>0:
        vDispM[i] += 1 if diffM>0 else -1
        diffM += -1 if diffM>0 else 1
        i = (i-1) % m

    quantities = [from_units(u) for u in qU]
    value_no_fee = [round(v/1000.0,3) for v in vM_noFee]
    monthly_fees = [round(inp.monthly_fee,3) for _ in range(m)]
    values = [round(v/1000.0,3) for v in vDispM]

    df = pd.DataFrame({
        "مسلسل": list(range(1, m+1)),
        "الشهر": [pd.Timestamp(x).strftime("%m/%Y") for x in months],
        "الكمية (م3)": [round(q,1) for q in quantities],
        "قيمة+دمغة بدون رسوم (ج)": value_no_fee,
        "الرسوم الشهرية (ج)": monthly_fees,
        "القيمة النهائية (ج)": values,
    })

    sums = {
        "q_sum": round(sum(quantities),1),
        "v_no_fee_sum": round(sum(value_no_fee),3),
        "v_fees_sum": round(sum(monthly_fees),3),
        "v_sum": round(sum(values),3),
        "q_target": q_target,
        "v_target": v_target,
    }

    return df, q_target, v_target, sums
