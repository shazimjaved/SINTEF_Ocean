"""Explicit QID-to-column and source mapping for the 2024 sensor export.

The short column names match the existing October pivot. Grouping is based on
registered QIDs and sources, never on fragments of a short name.
"""

CHANNELS = {
    # QID: (pivot column, source group)
    "1::0::14::0_1::2::0::8::0_3::0::3::0_8": ("ME_ScavAirPressure_bar", "onboard"),
    "1::0::15::0_1::2::0::3::0_1::0::6::0_8": ("ME_TC_RPM_Transducer", "onboard"),
    "1::0::25::0_1::2::0::8::0_20::0::1::0_8": ("ME_FuelLoad_pct", "onboard"),
    "2::0::11::0_1::1::0::3::0_12::0::1::0_8": ("SHAFT_Revolutions_TQ", "torquemeter"),
    "2::0::11::0_1::1::0::3::0_12::0::2::0_8": ("SHAFT_Torque_Nm_TQ", "torquemeter"),
    "2::0::11::0_1::1::0::3::0_14::0::1::0_8": ("SHAFT_MechPower_kW", "target"),
    "2::0::11::0_1::1::0::3::0_15::0::1::0_8": ("SHAFT_MechEnergy_kWh_TQ", "torquemeter"),
    "2::0::11::0_1::1::0::3::0_17::0::1::0_8": ("SHAFT_ThrustForce_kN_TQ", "torquemeter"),
    "2::0::11::0_1::1::0::3::0_1::0::6::0_8": ("SHAFT_RPM_TQ", "torquemeter"),
    "2::0::11::0_1::2::0::8::0_22::0::1::1_8": ("ME_FuelMassFlow_kghr_TQ", "torquemeter"),
    "2::0::1::0_1::1::0::7::0_1::0::4::22_8": ("WIND_RelSpeed_kn", "onboard"),
    "2::0::1::0_1::1::0::7::0_2::0::15::22_8": ("WIND_RelAngle_deg", "onboard"),
    "2::0::4::0_1::1::0::2::0_37::0::2::0_8": ("HULL_WaterDepth_m", "onboard"),
    "2::0::5::0_1::1::0::2::0_2::0::8::21_8": ("HULL_HeadingTrue_deg", "onboard"),
    "2::0::5::0_1::1::0::2::0_6::0::1::0_8": ("HULL_TurnRate_degmin", "onboard"),
    "2::0::6::1_1::1::0::2::0_1::0::1::0_8": ("SOG_kn", "onboard"),
    "2::0::7::0_1::1::0::2::0_1::0::5::11_8": ("STW_kn", "onboard"),
    "3::0::1::0_1::1::0::2::0_11::0::1::0_8": ("DRAFT_Fore_m", "faulty_draft"),
    "3::0::1::0_1::1::0::2::0_11::0::2::0_8": ("DRAFT_Aft_m", "faulty_draft"),
    "3::0::1::0_1::1::0::2::0_11::0::3::0_8": ("DRAFT_MidP_m", "faulty_draft"),
    "3::0::1::0_1::1::0::2::0_11::0::4::0_8": ("DRAFT_MidS_m", "faulty_draft"),
    "3::0::1::0_1::2::0::8::0_1::0::6::0_8": ("ME_RPM_CAMS", "onboard"),
    "4::0::4::0_1::1::0::7::0_1::0::4::21_8": ("WIND_TrueSpeed_kn_MB", "provider_mb"),
    "4::0::4::0_1::1::0::7::0_2::0::15::21_8": ("WIND_TrueAngle_deg_MB", "provider_mb"),
    "4::0::4::0_1::1::0::7::0_45::0::1::0_8": ("WAVE_SigHeight_m_MB", "provider_mb"),
    "4::0::4::0_1::1::0::7::0_45::0::2::0_8": ("SWELL_SigHeight_m_MB", "provider_mb"),
    "4::0::4::0_1::1::0::7::0_56::0::3::0_8": ("CURR_Eastward_ms_MB", "provider_mb"),
    "4::0::4::0_1::1::0::7::0_56::0::4::0_8": ("CURR_Northward_ms_MB", "provider_mb"),
    "4::0::8::0_1::1::0::7::0_2::0::18::21_8": ("WAVE_TrueAngle_deg_S", "provider_s"),
    "4::0::8::0_1::1::0::7::0_4::0::12::0_8": ("SEA_WaterTemp_C_S", "provider_s"),
    "4::0::8::0_1::1::0::7::0_40::0::2::0_8": ("WAVE_Period_sec_S", "provider_s"),
    "4::0::8::0_1::1::0::7::0_45::0::1::0_8": ("WAVE_SigHeight_m_S", "provider_s"),
    "4::0::8::0_1::1::0::7::0_56::0::3::0_8": ("CURR_Eastward_ms_S", "provider_s"),
    "4::0::8::0_1::1::0::7::0_56::0::4::0_8": ("CURR_Northward_ms_S", "provider_s"),
    "4::0::8::0_1::1::0::7::0_56::0::5::0_8": ("WIND_Eastward_ms_S", "provider_s"),
    "4::0::8::0_1::1::0::7::0_56::0::6::0_8": ("WIND_Northward_ms_S", "provider_s"),
}

COLUMN_TO_QID = {name: qid for qid, (name, _) in CHANNELS.items()}
COLUMN_TO_SOURCE = {name: source for _, (name, source) in CHANNELS.items()}
TARGET = "SHAFT_MechPower_kW"
LEAKAGE = {name for name, source in COLUMN_TO_SOURCE.items() if source == "torquemeter"}
DRAFT = {name for name, source in COLUMN_TO_SOURCE.items() if source == "faulty_draft"}
ENVIRONMENTAL = {name for name, source in COLUMN_TO_SOURCE.items()
                 if source in {"provider_mb", "provider_s"}}
ONBOARD = set(COLUMN_TO_SOURCE) - ENVIRONMENTAL
ANGLE_COLUMNS = {"HULL_HeadingTrue_deg", "WIND_RelAngle_deg",
                 "WIND_TrueAngle_deg_MB", "WAVE_TrueAngle_deg_S"}
MODEL_CANDIDATES = set(COLUMN_TO_SOURCE) - LEAKAGE - DRAFT - {TARGET, "HULL_WaterDepth_m"}

assert len(CHANNELS) == 36 and len(ENVIRONMENTAL) == 14
assert len(MODEL_CANDIDATES) == 24
assert "ME_ScavAirPressure_bar" in ONBOARD
