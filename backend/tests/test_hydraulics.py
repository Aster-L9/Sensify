import numpy as np

from app.sim.hydraulics import HydraulicInputs, solve_steady_state


def test_nominal_profile():
    s = solve_steady_state(HydraulicInputs(78.0, 62.0))
    assert np.allclose(s.pressure, [77.0, 74.0, 78.0, 74.0, 73.0, 62.0], atol=0.05)
    assert np.allclose(s.flow, 830.0, atol=0.5)


def test_operating_point_range():
    assert abs(solve_steady_state(HydraulicInputs(76.5, 63.5)).flow[0] - 774) < 5
    assert abs(solve_steady_state(HydraulicInputs(79.5, 60.5)).flow[0] - 882) < 5


def test_valve_closure_raises_upstream_pressure_and_cuts_flow():
    s = solve_steady_state(HydraulicInputs(78.0, 62.0, valve_open=0.25))
    assert s.flow[0] < 720 and s.pressure[3] > 76.5 and s.pressure[4] < 71.0


def test_leak_increases_upstream_flow_and_cuts_downstream_flow():
    s = solve_steady_state(HydraulicInputs(78.0, 62.0, leak_segment=3, leak_coeff=0.4 * 23.1))
    assert s.flow[2] > 870 and s.flow[3] < 805 and 70 < s.leak_flow < 90


def test_inlet_terminal_meters_receipt_flow_so_a_leak_there_is_visible():
    s = solve_steady_state(HydraulicInputs(78.0, 62.0, leak_segment=0, leak_coeff=0.7 * 23.1))
    assert s.flow[0] - s.flow[1] > 100 and abs(s.flow[0] - s.flow[1] - s.leak_flow) < 1


def test_pump_stop_and_blockage_reduce_flow():
    assert solve_steady_state(HydraulicInputs(78.0, 62.0, pump_speed=0.0)).flow[0] < 700
    b = solve_steady_state(HydraulicInputs(78.0, 62.0, block_segment=1, block_factor=3.0))
    assert b.flow[0] < 750 and b.pressure[1] < 71.0
