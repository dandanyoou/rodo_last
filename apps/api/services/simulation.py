"""1층 공통 행동 엔진 — 데이터 없이 돌아가는 최소 Social-Force-lite 구현.

Mesa 같은 외부 ABM 라이브러리 대신 순수 Python으로 구현했다 (design doc Open
Question: "1층 행동 엔진을 Mesa 라이브러리로 쓸지 자체 구현할지"는 아직 열려
있음 — 이 구현은 그 질문에 대한 "자체 구현" 답을 1차로 시도해본 것이다).
그리드 기반 밀도 근사로 O(N) per step을 유지해 5000 에이전트도 순수 Python
에서 감당 가능한 속도를 낸다 (NFR-10: 부스 50개/방문자 5천명 기준 5분 이내
[estimated] — 큰 입력에서는 여전히 벤치마크 필요).
"""

import math
import random
from collections import defaultdict

CELL_SIZE = 1.0  # meters
BASE_SPEED = 1.3  # m/s, 평균 보행 속도
DENSITY_K = 2.5  # 밀도에 따른 속도 저하 계수
BOOTH_ZONE_MARGIN = 1.0  # 부스 경계에서 혼잡도를 셀 때 여유 거리
REPEL_RADIUS = 1.2  # 부스(장애물)로부터 반발력이 작용하는 거리
REPEL_STRENGTH = 2.2  # Social Force 모델의 장애물 반발 항 — 지금까지 빠져 있던 부분
QUEUE_DENSITY_THRESHOLD = 15.0  # FR-13 포기 확률이 생기는 밀도 기준치.
# 주의: 이 값은 "실제 사람 밀도 명/㎡"가 아니라 이 모델이 셀(1m×1m) 단위로
# 재는 밀도 스케일에 맞춘 값이다 — 입장 파도·점 좌표 양자화 때문에 모델 내
# 밀도가 실제 인파 밀도보다 몇 배 높게 잡힌다. 실제 밀도 기준(3명/㎡)을 그대로
# 썼다가 거의 모든 방문에서 포기하는 버그가 났었다.
QUEUE_ABANDON_SLOPE = 0.04  # 임계치를 넘은 정도에 따른 포기 확률 증가율

STAY_TYPE_BASE_SECONDS = {
    "관람형": 20,
    "체험형": 90,
    "판매형": 60,
}


def _cell_key(x, y):
    return (int(x // CELL_SIZE), int(y // CELL_SIZE))


def _closest_point_on_rect(px, py, booth):
    cx = min(max(px, booth.x), booth.x + booth.w)
    cy = min(max(py, booth.y), booth.y + booth.h)
    return cx, cy


def _build_booth_grid(booths):
    """부스를 그리드 셀에 등록해둔다 — 에이전트가 매 스텝마다 전체 부스를
    다 검사하지 않고 자기 셀에 걸친 부스만 보게 하는 공간 분할.
    NFR-10(부스 50개/방문자 5천명) 규모에서 O(N*부스) 반발력 계산이
    병목이었다 (8개 부스로도 1500명에서 35초 — 50개면 5분을 넘길 위험)."""
    grid = defaultdict(list)
    for b in booths:
        x0 = int((b.x - REPEL_RADIUS) // CELL_SIZE)
        x1 = int((b.x + b.w + REPEL_RADIUS) // CELL_SIZE)
        y0 = int((b.y - REPEL_RADIUS) // CELL_SIZE)
        y1 = int((b.y + b.h + REPEL_RADIUS) // CELL_SIZE)
        for cx in range(x0, x1 + 1):
            for cy in range(y0, y1 + 1):
                grid[(cx, cy)].append(b)
    return grid


def _booths_in_zone(booth, x, y):
    return (
        booth.x - BOOTH_ZONE_MARGIN <= x <= booth.x + booth.w + BOOTH_ZONE_MARGIN
        and booth.y - BOOTH_ZONE_MARGIN <= y <= booth.y + booth.h + BOOTH_ZONE_MARGIN
    )


class Agent:
    __slots__ = ("x", "y", "targets", "target_idx", "dwell_left", "in_booth", "visited", "done")

    def __init__(self, x, y, targets):
        self.x = x
        self.y = y
        self.targets = targets  # list of (booth_or_None, goal_x, goal_y, stay_seconds)
        self.target_idx = 0
        self.dwell_left = 0.0
        self.in_booth = None
        self.visited = set()
        self.done = False

    def current_goal(self):
        if self.target_idx >= len(self.targets):
            return None
        return self.targets[self.target_idx]


def _pick_route(booths, entrance, exit_pt, rng):
    """부스 2~4개를 무작위로 골라 입구->부스들->출구 순서의 목표 리스트를 만든다."""
    k = min(len(booths), rng.randint(2, 4))
    chosen = rng.sample(booths, k) if booths else []
    targets = []
    for b in chosen:
        cx, cy = b.x + b.w / 2, b.y + b.h / 2
        stay = STAY_TYPE_BASE_SECONDS.get(b.stay_type, 30) * rng.uniform(0.7, 1.3)
        targets.append((b, cx, cy, stay))
    targets.append((None, exit_pt[0], exit_pt[1], 0))
    return targets


def run_simulation(venue, layout, booths, visitor_count, seed=None, dt=1.0, max_seconds=1800):
    """venue/layout은 치수와 입/출구를, booths는 Booth 행 목록을 받는다.

    반환값: dict(booth_stats, bottleneck_ranking, overall_congestion_score)
    """
    rng = random.Random(seed)
    entrance = (layout.entrance_x, layout.entrance_y)
    exit_pt = (layout.exit_x, layout.exit_y)

    agents = []
    arrival_wave = max(1, visitor_count // 60)  # 입장은 ~60틱에 걸쳐 분산 (입구 몰림 완화)
    pending = list(range(visitor_count))

    booth_dwell_totals = defaultdict(float)
    booth_visit_counts = defaultdict(int)
    cell_max_density = defaultdict(float)
    booth_grid = _build_booth_grid(booths)

    t = 0.0
    steps = 0
    max_steps = int(max_seconds / dt)
    while (pending or agents) and steps < max_steps:
        # 새 방문객 입장 (파도형 입장 분포, dev spec FR-10)
        for _ in range(min(arrival_wave, len(pending))):
            pending.pop()
            targets = _pick_route(booths, entrance, exit_pt, rng)
            # 입구 한 점에 전원이 겹쳐 밀도가 비현실적으로 치솟지 않도록 약간의
            # 지터를 준다 (실제 입구는 폭이 있는 문/통로이지 좌표 하나가 아니다).
            jx = entrance[0] + rng.uniform(-1.0, 1.0)
            jy = entrance[1] + rng.uniform(-1.0, 1.0)
            agents.append(Agent(jx, jy, targets))

        # 그리드 밀도 계산 (O(N) per step)
        cell_counts = defaultdict(int)
        for a in agents:
            cell_counts[_cell_key(a.x, a.y)] += 1
        cell_area = CELL_SIZE * CELL_SIZE
        for key, cnt in cell_counts.items():
            density = cnt / cell_area
            if density > cell_max_density[key]:
                cell_max_density[key] = density

        next_agents = []
        for a in agents:
            goal = a.current_goal()
            if goal is None:
                continue  # 퇴장 완료
            booth, gx, gy, stay = goal

            if a.dwell_left > 0:
                a.dwell_left -= dt
                if a.dwell_left <= 0 and booth is not None:
                    booth_dwell_totals[booth.id] += stay
                    booth_visit_counts[booth.id] += 1
                    a.target_idx += 1
                next_agents.append(a)
                continue

            dx, dy = gx - a.x, gy - a.y
            dist = math.hypot(dx, dy)
            if dist < 0.3:
                if booth is not None and booth.id not in a.visited:
                    # FR-13: 대기열이 길면 우회/포기. 부스 바로 앞 밀집도가
                    # 기준을 넘으면 일정 확률로 포기하고 다음 목표로 넘어간다.
                    local_density = cell_counts[_cell_key(a.x, a.y)] / cell_area
                    abandon_p = min(0.9, max(0.0, (local_density - QUEUE_DENSITY_THRESHOLD) * QUEUE_ABANDON_SLOPE))
                    if abandon_p > 0 and rng.random() < abandon_p:
                        a.target_idx += 1
                        goal = a.current_goal()
                        if goal is None:
                            continue  # 퇴장
                        next_agents.append(a)
                        continue
                    a.visited.add(booth.id)
                    a.dwell_left = stay
                    next_agents.append(a)
                    continue
                a.target_idx += 1
                goal = a.current_goal()
                if goal is None:
                    continue  # 퇴장
                next_agents.append(a)
                continue

            density_here = cell_counts[_cell_key(a.x, a.y)] / cell_area
            speed = BASE_SPEED / (1.0 + DENSITY_K * density_here)

            # 장애물(부스) 반발력 — 지금 향하는 부스가 아닌 다른 부스는 뚫고
            # 지나갈 수 없는 물리적 장애물이다. Social Force 모델의 핵심 항인데
            # 지금까지는 밀집도 기반 속도저하만 있고 이게 빠져 있었다.
            desired_x, desired_y = dx / dist, dy / dist
            rep_x, rep_y = 0.0, 0.0
            for ob in booth_grid.get(_cell_key(a.x, a.y), ()):
                if booth is not None and ob.id == booth.id:
                    continue
                ox, oy = _closest_point_on_rect(a.x, a.y, ob)
                odx, ody = a.x - ox, a.y - oy
                odist = math.hypot(odx, ody)
                if 1e-6 < odist < REPEL_RADIUS:
                    force = REPEL_STRENGTH * (REPEL_RADIUS - odist) / REPEL_RADIUS
                    rep_x += odx / odist * force
                    rep_y += ody / odist * force

            move_x, move_y = desired_x + rep_x, desired_y + rep_y
            norm = math.hypot(move_x, move_y)
            if norm > 1e-6:
                move_x, move_y = move_x / norm, move_y / norm
            else:
                move_x, move_y = desired_x, desired_y

            step = min(speed * dt, dist)
            a.x += move_x * step
            a.y += move_y * step
            next_agents.append(a)

        agents = next_agents
        t += dt
        steps += 1

    # 부스별 통계
    booth_stats = {}
    for b in booths:
        visits = booth_visit_counts.get(b.id, 0)
        total_dwell = booth_dwell_totals.get(b.id, 0.0)
        booth_stats[b.id] = {
            "name": b.name,
            "avg_dwell_s": round(total_dwell / visits, 1) if visits else 0.0,
            "visit_ratio": round(visits / visitor_count, 3) if visitor_count else 0.0,
        }

    # 부스 구역(margin 포함) 안의 셀 중 최대 밀도를 부스의 혼잡도로 집계
    bottleneck_ranking = []
    for b in booths:
        max_density = 0.0
        for (cx, cy), density in cell_max_density.items():
            wx, wy = (cx + 0.5) * CELL_SIZE, (cy + 0.5) * CELL_SIZE
            if _booths_in_zone(b, wx, wy) and density > max_density:
                max_density = density
        bottleneck_ranking.append({"booth_id": b.id, "name": b.name, "congestion_score": round(max_density, 3)})

    # 부스 구역 밖(복도)의 전역 최대 밀도도 "일반 구역" 항목으로 추가
    corridor_max = 0.0
    for (cx, cy), density in cell_max_density.items():
        wx, wy = (cx + 0.5) * CELL_SIZE, (cy + 0.5) * CELL_SIZE
        if not any(_booths_in_zone(b, wx, wy) for b in booths) and density > corridor_max:
            corridor_max = density
    bottleneck_ranking.append({"booth_id": None, "name": "복도/일반 구역", "congestion_score": round(corridor_max, 3)})

    bottleneck_ranking.sort(key=lambda r: r["congestion_score"], reverse=True)
    overall_congestion_score = round(sum(r["congestion_score"] for r in bottleneck_ranking[:3]), 3)

    # 캔버스 히트맵용 원본 셀 데이터 (정규화는 프론트에서 — 레이아웃마다 최대
    # 밀도가 다르므로 비교 화면에서는 두 배치안 공통 스케일로 맞춰야 한다).
    heatmap_cells = [
        {"x": round((cx + 0.5) * CELL_SIZE, 2), "y": round((cy + 0.5) * CELL_SIZE, 2), "density": round(density, 3)}
        for (cx, cy), density in cell_max_density.items()
        if density > 0
    ]

    return {
        "booth_stats": booth_stats,
        "bottleneck_ranking": bottleneck_ranking,
        "overall_congestion_score": overall_congestion_score,
        "heatmap_cells": heatmap_cells,
        "cell_size": CELL_SIZE,
    }
