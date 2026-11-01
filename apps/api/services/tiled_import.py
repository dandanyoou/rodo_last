"""Tiled 맵 에디터 JSON export를 Digital Twin(Venue/Layout/Booth)으로 변환.

Approach C(하이브리드)의 핵심 전제: "자체 Canvas 에디터는 생략하고 Tiled로
배치도를 만든다". Tiled 표준 맵 JSON(layers[].objects[])을 1차로 지원하고,
Tiled 파일이 아직 없을 때를 위해 단순화된 커스텀 JSON 스키마도 받는다
(design doc Dependencies: "Mesa(또는 자체 Social Force 구현)와 Tiled 맵
에디터 포맷 호환성 확인"은 여전히 열려 있는 질문 — 실제 Tiled export로는
아직 검증 전이다).
"""


class LayoutImportError(ValueError):
    pass


def parse_layout_json(data):
    """data(dict)를 받아 (venue_dims, entrance, exit, booths) 튜플로 변환한다.

    booths는 [{"name", "x", "y", "w", "h", "stay_type"}, ...] 형태.
    """
    if "layers" in data:
        return _parse_tiled(data)
    if "venue" in data and "booths" in data:
        return _parse_simple(data)
    raise LayoutImportError(
        "인식할 수 없는 배치도 형식입니다. Tiled 맵 JSON(layers 포함) 또는 "
        "단순 스키마({venue, entrance, exit, booths})만 지원합니다."
    )


def _parse_simple(data):
    venue = data["venue"]
    width = float(venue["width"])
    height = float(venue["height"])
    entrance = data.get("entrance", {"x": 0, "y": height / 2})
    exit_pt = data.get("exit", {"x": width, "y": height / 2})
    booths = []
    for b in data["booths"]:
        booths.append(
            {
                "name": b["name"],
                "x": float(b["x"]),
                "y": float(b["y"]),
                "w": float(b.get("w", 2)),
                "h": float(b.get("h", 2)),
                "stay_type": b.get("stay_type", "관람형"),
            }
        )
    return (width, height), (float(entrance["x"]), float(entrance["y"])), (
        float(exit_pt["x"]),
        float(exit_pt["y"]),
    ), booths


def _parse_tiled(data):
    tile_w = data.get("tilewidth", 1) or 1
    tile_h = data.get("tileheight", 1) or 1
    width = float(data.get("width", 0)) * tile_w
    height = float(data.get("height", 0)) * tile_h

    entrance = None
    exit_pt = None
    booths = []

    for layer in data.get("layers", []):
        if layer.get("type") != "objectgroup":
            continue
        for obj in layer.get("objects", []):
            name = (obj.get("name") or "").strip()
            lname = name.lower()
            x = float(obj.get("x", 0))
            y = float(obj.get("y", 0))
            w = float(obj.get("width", 0)) or 0.0
            h = float(obj.get("height", 0)) or 0.0
            cx, cy = x + w / 2, y + h / 2

            if lname == "entrance":
                entrance = (cx if w else x, cy if h else y)
                continue
            if lname == "exit":
                exit_pt = (cx if w else x, cy if h else y)
                continue

            stay_type = "관람형"
            for prop in obj.get("properties", []) or []:
                if prop.get("name") == "stay_type":
                    stay_type = prop.get("value", stay_type)

            booths.append(
                {
                    "name": name or f"booth-{len(booths) + 1}",
                    "x": x,
                    "y": y,
                    "w": w or 2.0,
                    "h": h or 2.0,
                    "stay_type": stay_type,
                }
            )

    if width <= 0 or height <= 0:
        raise LayoutImportError("Tiled 맵의 width/height를 읽을 수 없습니다 (map JSON이 맞는지 확인하세요).")
    if entrance is None:
        entrance = (0.0, height / 2)
    if exit_pt is None:
        exit_pt = (width, height / 2)
    if not booths:
        raise LayoutImportError("objectgroup 레이어에서 부스를 하나도 찾지 못했습니다.")

    return (width, height), entrance, exit_pt, booths
