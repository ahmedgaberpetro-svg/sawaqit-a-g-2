# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
from datetime import date, datetime
from core import Inputs, distribute, tiers_from_p1

st.set_page_config(page_title="حساب استهلاكات السواقط", layout="wide")

# عنوان أعلى الصفحة بدون مسافة كبيرة
st.markdown("<h2 style='text-align:center;margin-top:-10px;'>حساب استهلاكات السواقط</h2>", unsafe_allow_html=True)

# كروت F8/F9 جنب بعض
c_top1, c_top2 = st.columns(2, gap="small")
with c_top1:
    target_q_box = st.empty()
with c_top2:
    target_v_box = st.empty()

# تقسيم المعطيات والمخرجات: المعطيات يسار، المخرجات يمين (عكس السابق)
col_inputs, col_outputs = st.columns([1.2, 1.1], gap="large")

def num(v: str) -> float:
    v = (v or "").strip().replace(",", ".")
    if v in ("", None): return 0.0
    try:
        return float(v)
    except:
        return 0.0

with col_inputs:
    st.markdown("### **المعطيات**")
    left, right = st.columns(2, gap="small")
    with left:
        st.markdown("#### نهاية الفترة")
        edate = st.date_input("تاريخ قراءة نهاية الفترة", value=date.today())
        b3 = st.text_input("الاستهلاك الكلي (نهاية)", value="")
        c3 = st.text_input("استهلاك الشهر السابق (نهاية)", value="")
        d3 = st.text_input("الاستهلاك الحالي (نهاية)", value="")
        e3 = st.text_input("الرصيد الحالي (نهاية)", value="")
        c8 = st.text_input("قيمة الشحنة (الثانية)", value="")
    with right:
        st.markdown("#### بداية الفترة")
        sdate = st.date_input("تاريخ قراءة بداية الفترة", value=date.today().replace(day=1))
        b2 = st.text_input("الاستهلاك الكلي (بداية)", value="")
        c2 = st.text_input("استهلاك الشهر السابق (بداية)", value="")
        d2 = st.text_input("الاستهلاك الحالي (بداية)", value="")
        e2 = st.text_input("الرصيد الحالي (بداية)", value="")
        c7 = st.text_input("قيمة الشحنة (الأولى)", value="")

    # صف صغير للرسوم والدمغة وعدد شهور صفر
    r1, r2, r3 = st.columns([1,1,1], gap="small")
    with r1:
        monthly_fee = st.selectbox("الرسوم الشهرية", options=[6.20,7.10,12.0,13.68,17.5,19.5,0.0,"حر"], index=0)
        if monthly_fee == "حر":
            monthly_fee = num(st.text_input("رسوم مخصصة", value=""))
        else:
            monthly_fee = float(monthly_fee)
    with r2:
        st.text_input("دمغة الاستهلاك (ثابتة)", value="0.036", disabled=True)
        stamp = 0.036
    with r3:
        zero_tail = int(num(st.text_input("عدد الشهور بدون استهلاك", value="0")))

    # اختيار الشريحة الأولى → الثانية والثالثة تُحسب تلقائيًا وتُعرض ككابتشن
    p1 = st.selectbox("سعر الشريحة (الأولى)", [2.35,2.50,2.60,3.00,4.00], index=1)
    p2_calc, p3_calc = tiers_from_p1(p1)
    st.caption(f"سعر الشريحة الثانية: {p2_calc:.2f} — الثالثة: {p3_calc:.2f}")

    # زر احسب (شكل مميز)
    st.markdown(
        """
        <style>
        .calc-btn > button {background: linear-gradient(90deg,#059669,#10b981); color:#fff; 
                            border-radius:14px; box-shadow:0 6px 18px rgba(16,185,129,0.35); height:52px; font-weight:700;}
        </style>
        """,
        unsafe_allow_html=True
    )
    go = st.container()
    with go:
        pressed = st.button("احسب", type="primary", use_container_width=True)

with col_outputs:
    st.markdown("### **المخرجات**")
    out_placeholder = st.empty()
    dl_placeholder = st.empty()
    sums_placeholder = st.empty()

if pressed:
    inp = Inputs(
        start_date=pd.Timestamp(sdate),
        end_date=pd.Timestamp(edate),
        B2_STOT=num(b2),
        C2_SPREV=num(c2),
        D2_SCUR=num(d2),
        E2_START_BAL=num(e2),
        B3_ETOT=num(b3),
        C3_EPREV=num(c3),
        D3_ECUR=num(d3),
        E3_END_BAL=num(e3),
        topup1_net=num(c7),
        topup2_net=num(c8),
        p1=p1, p2=0.0, p3=0.0,
        stamp=stamp,
        monthly_fee=monthly_fee,
        zero_tail=zero_tail
    )
    df, q_target, v_target, sums = distribute(inp)

    target_q_box.markdown(f"<div style='background:#065f46;color:#fff;padding:10px;border-radius:12px;text-align:center;'><b>الكمية المستهدفة</b> (م³): {q_target:.1f}</div>", unsafe_allow_html=True)
    target_v_box.markdown(f"<div style='background:#0e7490;color:#fff;padding:10px;border-radius:12px;text-align:center;'><b>القيمة المستهدفة</b> (ج): {v_target:.3f}</div>", unsafe_allow_html=True)

    # عرض الجدول مع تصغير الأعمدة
    out_placeholder.dataframe(df, use_container_width=True, hide_index=True)

    # إجمالي سطر مخصص (نموذج مبسط): نعرض القيم تحت الجدول
    sums_placeholder.write({
        "مجموع الكميات": round(float(sums["q_sum"]),1),
        "مجموع قيمة بدون رسوم": round(float(sums["v_no_fee_sum"]),3),
        "مجموع الرسوم الشهرية": round(float(sums["v_fees_sum"]),3),
        "مجموع القيم النهائية": round(float(sums["v_sum"]),3),
        "تطابق الكمية": f'{sums["q_sum"]} == {sums["q_target"]}',
        "تطابق القيمة (نهائي)": f'{sums["v_sum"]} == {sums["v_target"]}',
    })

    # حفظ وتنزيل
    xlsx = "/mnt/data/swaqat_result.xlsx"
    csv  = "/mnt/data/swaqat_result.csv"
    with pd.ExcelWriter(xlsx, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="نتيجة التوزيع")
    df.to_csv(csv, index=False, encoding="utf-8-sig")
    dl_placeholder.download_button("تحميل Excel", data=open(xlsx,"rb").read(), file_name="swaqat_result.xlsx")
    dl_placeholder.download_button("تحميل CSV", data=open(csv,"rb").read(), file_name="swaqat_result.csv")
else:
    target_q_box.markdown("<div style='background:#065f46;color:#fff;padding:10px;border-radius:12px;text-align:center;'><b>الكمية المستهدفة</b> (م³): —</div>", unsafe_allow_html=True)
    target_v_box.markdown("<div style='background:#0e7490;color:#fff;padding:10px;border-radius:12px;text-align:center;'><b>القيمة المستهدفة</b> (ج): —</div>", unsafe_allow_html=True)
