from __future__ import annotations

from typing import Dict, Optional, Tuple


TABLE7: Dict[str, Dict[str, int]] = {
    "declared":  {"lcb0": 102, "lcb1": 95, "lcb2": 88, "lcb3": 95, "lcb4": 99,
                  "lcb5": 98, "lcb6": 92, "lcb7": 84, "lcb8": 88, "lcb9": 97},
    "zero":      {"lcb0": 102, "lcb1": 95, "lcb2": 91, "lcb3": 95, "lcb4": 101,
                  "lcb5": 105, "lcb6": 92, "lcb7": 86, "lcb8": 92, "lcb9": 100},
    "unlimited": {"lcb0": 102, "lcb1": 88, "lcb2": 88, "lcb3": 95, "lcb4": 93,
                  "lcb5": 95, "lcb6": 88, "lcb7": 84, "lcb8": 86, "lcb9": 94},
}
TABLE7_AVERAGES = {"declared": 93.8, "zero": 95.9, "unlimited": 91.3}


TABLE8: Dict[str, Dict[str, int]] = {
    "10":  {"t_0": 107, "t_1": 103, "t_2": 107, "t_3": 114, "t_4": 116,
            "t_5": 108, "t_6": 105, "t_7": 118, "t_8": 118, "t_9": 119},
    "25":  {"t_0": 101, "t_1": 101, "t_2": 102, "t_3": 105, "t_4": 110,
            "t_5": 101, "t_6": 98, "t_7": 114, "t_8": 115, "t_9": 115},
    "50":  {"t_0": 100, "t_1": 97, "t_2": 102, "t_3": 99, "t_4": 108,
            "t_5": 99, "t_6": 97, "t_7": 113, "t_8": 112, "t_9": 110},
    "75":  {"t_0": 100, "t_1": 97, "t_2": 101, "t_3": 99, "t_4": 107,
            "t_5": 99, "t_6": 97, "t_7": 112, "t_8": 112, "t_9": 110},
    "100": {"t_0": 100, "t_1": 97, "t_2": 101, "t_3": 99, "t_4": 107,
            "t_5": 99, "t_6": 97, "t_7": 112, "t_8": 112, "t_9": 110},
}


TABLE9: Dict[str, Dict[str, int]] = {
    "small":     {"r_0": 82, "r_1": 69, "r_2": 54, "r_3": 69, "r_4": 64,
                  "r_5": 72, "r_6": 72, "r_7": 99, "r_8": 79, "r_9": 74},
    "large":     {"r_0": 71, "r_1": 65, "r_2": 54, "r_3": 65, "r_4": 62,
                  "r_5": 70, "r_6": 69, "r_7": 85, "r_8": 71, "r_9": 63},
    "unlimited": {"r_0": 63, "r_1": 37, "r_2": 33, "r_3": 50, "r_4": 45,
                  "r_5": 53, "r_6": 42, "r_7": 57, "r_8": 65, "r_9": 44},
}
TABLE9_AVERAGES = {"small": 73.4, "large": 67.5, "unlimited": 48.9}


TABLE10: Dict[str, Tuple[int, int, int]] = {
    "lcbrtu_0": (293, 352, 345), "lcbrtu_1": (299, 312, 312),
    "lcbrtu_2": (258, 280, 278), "lcbrtu_3": (297, 411, 405),
    "lcbrtu_4": (288, 322, 314), "lcbrtu_5": (276, 359, 356),
    "lcbrtu_6": (283, 299, 297), "lcbrtu_7": (264, 290, 288),
    "lcbrtu_8": (256, 406, 390), "lcbrtu_9": (294, 305, 305),
}
TABLE10_AVERAGES = {"cp": 333.6, "alns": 329.0}


CONFIG: Dict[Tuple[str, str], dict] = {}
for _m in ("declared", "zero", "unlimited"):
    CONFIG[("exp1", _m)] = dict(folder="Experiment 1", machine_buffers=_m,
                                tools=False, utilities=False, resources=False,
                                wip=False)
for _b in ("10", "25", "50", "75"):
    CONFIG[("exp2", _b)] = dict(folder=f"Experiment 2/{_b}",
                                machine_buffers="off", tools=True,
                                utilities=False, resources=False, wip=False)
CONFIG[("exp2", "100")] = dict(folder="Experiment 2/75", machine_buffers="off",
                               tools=False, utilities=False, resources=False,
                               wip=False)
CONFIG[("exp3", "small")] = dict(folder="Experiment 3/50", machine_buffers="off",
                                 tools=False, utilities=False, resources=True,
                                 wip=True)
CONFIG[("exp3", "large")] = dict(folder="Experiment 3/100", machine_buffers="off",
                                 tools=False, utilities=False, resources=True,
                                 wip=True)
CONFIG[("exp3", "none")] = dict(folder="Experiment 3/50", machine_buffers="off",
                                tools=False, utilities=False, resources=False,
                                wip=False)
CONFIG[("exp4", "all")] = dict(folder="Experiment 4", machine_buffers="declared",
                               tools=True, utilities=True, resources=True,
                               wip=True)


def published_for(experiment: str, stem: str, config: str) -> Optional[int]:
    if experiment == "exp1":
        return TABLE7[config][stem]
    if experiment == "exp2":
        return TABLE8[config][stem]
    if experiment == "exp3":
        return TABLE9[{"small": "small", "large": "large",
                       "none": "unlimited"}[config]][stem]
    return None
