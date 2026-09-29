"""리더보드 리플레이: 양쪽 자원 흐름 (수입·점령 비용·깃발병/전투병 생산·깃발병 손실) 구간별.
우리 생산 = SPAWN 명령을 직전 자원으로 실제 처리한 수(엔진 순서: 생산 → 이동 → 전투 → 수입 → 점령 → 보급소).
상대 생산: 유닛 지출 = 직전 자원 + 수입 − 점령 비용 + 보급소 − 지금 자원. 전투병은 1:1 상쇄라
상대 전투병 사망 = 우리 전투병 사망 → 상대 전투병 생산 = 증감 + 사망, 깃발병 생산 = (지출 − 전투병 값 × 전투병 생산) / 5.

사용법 (저장소 최상위에서):
    python scripts/replay_economy.py data/server-replays/2026-09-29_leaderboard_10/*패.json
"""
import json, sys, re, os
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent / "data" / "server-replays"
WINDOWS = [(1, 20), (21, 50), (51, 80), (81, 120), (121, 160)]

def owned(obs, team, kind=None):
    return [b for b in obs["buildings"] if b["owner"] == team and (kind is None or b["type"] == kind)]

def count(obs, team, kind):
    return sum(u[4] for u in obs["units"] if u[0] == team and u[1] == kind)

def analyze(path):
    d = json.load(open(path, encoding="utf-8"))
    me = d["side"]; op = "K" if me == "Y" else "Y"
    T = d["turns"]
    rows = []  # per turn dict per team
    depot = {me: set(), op: set()}
    for i in range(1, len(T)):
        prev, cur = T[i - 1]["observation"], T[i]["observation"]
        r = {}
        # capture spend per team
        cap = {me: 0, op: 0}; dep = {me: 0, op: 0}; ncap = {me: 0, op: 0}; nneu = {me: 0, op: 0}
        for e in cur["events"]:
            if e["kind"] not in ("capture", "neutral"):
                continue
            t = e["team"]
            b = next(bb for bb in cur["buildings"] if bb["id"] == e["buildingId"])
            onit = any(u[0] == t and u[1] == "F" and u[2] == e["x"] and u[3] == e["y"] for u in cur["units"])
            if e["kind"] == "neutral" and not onit:
                continue  # 깃발 뽑힘: 비용 없음
            base = 4 if b["type"] == "PLAZA" else 2
            lib = bool(owned(prev, t, "LIBRARY"))
            cap[t] += max(1, base - (1 if lib else 0))
            if e["kind"] == "capture":
                ncap[t] += 1
                if b["type"] == "DEPOT" and b["id"] not in depot[t]:
                    depot[t].add(b["id"]); dep[t] += 15
            else:
                nneu[t] += 1
        for t in (me, op):
            inc = 10 + 2 * len(owned(prev, t, "HALL"))
            wc = max(2, 3 - len(owned(prev, t, "ENG")))
            unit = prev["resources"][t] + inc - cap[t] + dep[t] - cur["resources"][t]
            r[t] = dict(inc=inc, cap=cap[t], unit=unit, wc=wc, ncap=ncap[t], nneu=nneu[t],
                        F=count(cur, t, "F"), W=count(cur, t, "W"), S=count(cur, t, "S"),
                        dF=count(cur, t, "F") - count(prev, t, "F"), dW=count(cur, t, "W") - count(prev, t, "W"),
                        bld=len(owned(cur, t)), res=cur["resources"][t])
        # 우리 생산: 명령 그대로 처리
        res = prev["resources"][me]; wc = r[me]["wc"]; sp = {"F": 0, "W": 0, "S": 0}
        cost = {"F": 5, "W": wc, "S": 2}
        for ln in (T[i].get("command") or {}).get("lines", []):
            m = re.match(r"SPAWN ([FWS]) (\d+)", ln)
            if m:
                k, n = m.group(1), int(m.group(2)); made = min(n, res // cost[k]); res -= made * cost[k]; sp[k] += made
        r[me].update(spF=sp["F"], spW=sp["W"], spS=sp["S"])
        wdead = sp["W"] - r[me]["dW"]
        spW = r[op]["dW"] + wdead
        spF = (r[op]["unit"] - r[op]["wc"] * spW) / 5
        r[op].update(spF=spF, spW=spW, spS=0)
        for t in (me, op):
            r[t]["Fdead"] = r[t]["spF"] - r[t]["dF"]
        rows.append(r)
    return d, me, op, rows

def summarize(rows, t, a, b):
    sel = [r[t] for i, r in enumerate(rows, 1) if a <= i <= b and i <= len(rows)]
    if not sel: return None
    s = lambda k: sum(x[k] for x in sel)
    return dict(inc=s("inc"), cap=s("cap"), unit=s("unit"), spF=s("spF"), spW=s("spW"), Fdead=s("Fdead"),
                ncap=s("ncap"), nneu=s("nneu"), F=sel[-1]["F"], W=sel[-1]["W"], bld=sel[-1]["bld"],
                Favg=sum(x["F"] for x in sel) / len(sel))

if __name__ == "__main__":
    files = sys.argv[1:]
    for f in files:
        d, me, op, rows = analyze(f)
        name = os.path.basename(f)[:-5]
        print(f"\n## {os.path.basename(os.path.dirname(f))} {name}  ({d['result']['reason']}, {len(rows)}턴)")
        print("구간      | 수입 우:상 | 점령비 우:상 | 유닛지출 우:상 | F생산 우:상 | W생산 우:상 | F손실 우:상 | 점령/중립화 우:상 | 끝 F 우:상 | 끝 W 우:상 | 끝 건물 우:상")
        for a, b in WINDOWS:
            m, o = summarize(rows, me, a, b), summarize(rows, op, a, b)
            if not m: break
            print(f"{a:3}-{b:3}   | {m['inc']}:{o['inc']} | {m['cap']}:{o['cap']} | {m['unit']}:{o['unit']} | "
                  f"{m['spF']}:{o['spF']:.0f} | {m['spW']}:{o['spW']} | {m['Fdead']:.0f}:{o['Fdead']:.0f} | "
                  f"{m['ncap']}/{m['nneu']}:{o['ncap']}/{o['nneu']} | {m['F']}:{o['F']} | {m['W']}:{o['W']} | {m['bld']}:{o['bld']}")
