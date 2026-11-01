import json


def test_health(client):
    res = client.get("/")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_create_and_list_venues(client):
    res = client.post("/venues", json={"name": "테스트 행사장", "width": 60.0, "height": 40.0})
    assert res.status_code == 201
    venue_id = res.json()["id"]

    res = client.get("/venues")
    assert res.status_code == 200
    assert any(v["id"] == venue_id for v in res.json())


def test_upload_layout(client, tmp_path):
    layout_data = {
        "venue": {"width": 60, "height": 40},
        "entrance": {"x": 0, "y": 20},
        "exit": {"x": 60, "y": 20},
        "booths": [
            {"name": "A", "x": 10, "y": 10, "w": 4, "h": 4, "stay_type": "관람형"},
            {"name": "B", "x": 20, "y": 10, "w": 4, "h": 4, "stay_type": "체험형"},
        ],
    }
    layout_file = tmp_path / "layout.json"
    layout_file.write_text(json.dumps(layout_data))

    with open(layout_file, "rb") as f:
        res = client.post(
            "/layouts/upload",
            data={"venue_name": "테스트", "layout_name": "A안"},
            files={"layout_file": ("layout.json", f, "application/json")},
        )
    assert res.status_code == 201
    body = res.json()
    assert body["name"] == "A안"
    assert len(body["booths"]) == 2


def test_simrun_lifecycle(client, tmp_path):
    layout_data = {
        "venue": {"width": 30, "height": 20},
        "entrance": {"x": 0, "y": 10},
        "exit": {"x": 30, "y": 10},
        "booths": [{"name": "X", "x": 5, "y": 5, "w": 3, "h": 3, "stay_type": "관람형"}],
    }
    layout_file = tmp_path / "l.json"
    layout_file.write_text(json.dumps(layout_data))

    with open(layout_file, "rb") as f:
        layout_id = client.post(
            "/layouts/upload",
            data={"venue_name": "V", "layout_name": "L"},
            files={"layout_file": ("l.json", f, "application/json")},
        ).json()["id"]

    res = client.post(f"/layouts/{layout_id}/simruns", json={"visitor_count": 50})
    assert res.status_code == 201
    simrun_id = res.json()["id"]

    res = client.get(f"/simruns/{simrun_id}")
    assert res.status_code == 200
    assert res.json()["id"] == simrun_id
