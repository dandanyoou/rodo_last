"""휴대폰 영상 -> 희소 3D 점군 재구성. rodo/scan_reconstruct.py에서 포팅.

메싱(점 -> 면) 단계는 open3d가 필요한데 cv2와 같은 환경에 못 들어간다.
MESH_VENV_PYTHON 환경변수로 별도 venv의 파이썬 경로를 지정하면 메싱을 실행하고,
없으면 점군만으로 처리한다.
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import cv2
import numpy as np

_MESH_VENV_PYTHON = os.environ.get("MESH_VENV_PYTHON", "")
_MESH_SCRIPT = Path(__file__).parent.parent.parent.parent / "prototypes" / "mesh_from_cloud.py"

MAX_POINTS_PER_PAIR = 2000
REPROJ_ERROR_THRESHOLD = 4.0


class ReconstructionError(ValueError):
    pass


def extract_frames(video_path: Path, out_dir: Path, fps: float = 2.0):
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-i", str(video_path), "-vf", f"fps={fps},scale=960:-1",
         "-q:v", "3", str(out_dir / "frame_%04d.jpg"), "-y"],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return sorted(out_dir.glob("frame_*.jpg"))


def approx_intrinsics(width, height):
    f = max(width, height)
    return np.array([[f, 0, width / 2], [0, f, height / 2], [0, 0, 1]], dtype=np.float64)


def match_features(orb, matcher, img1, img2):
    kp1, des1 = orb.detectAndCompute(img1, None)
    kp2, des2 = orb.detectAndCompute(img2, None)
    if des1 is None or des2 is None or len(kp1) < 20 or len(kp2) < 20:
        return None
    raw_matches = matcher.knnMatch(des1, des2, k=2)
    good = [m for pair in raw_matches if len(pair) == 2 for m, n in [pair] if m.distance < 0.75 * n.distance]
    if len(good) < 30:
        return None
    return (
        np.float32([kp1[m.queryIdx].pt for m in good]),
        np.float32([kp2[m.trainIdx].pt for m in good]),
    )


def reconstruct(video_path: Path, fps: float = 4.0):
    with tempfile.TemporaryDirectory() as tmp:
        frames = extract_frames(video_path, Path(tmp), fps=fps)
        if len(frames) < 5:
            raise ReconstructionError("프레임이 너무 적습니다(5장 미만) — 영상이 너무 짧습니다.")

        first = cv2.imread(str(frames[0]), cv2.IMREAD_GRAYSCALE)
        h, w = first.shape
        K = approx_intrinsics(w, h)
        orb = cv2.ORB_create(nfeatures=3000)
        matcher = cv2.BFMatcher(cv2.NORM_HAMMING)

        global_R, global_t = np.eye(3), np.zeros((3, 1))
        all_points = []
        camera_count = 1
        prev_img = first

        for i in range(1, len(frames)):
            curr_img = cv2.imread(str(frames[i]), cv2.IMREAD_GRAYSCALE)
            matched = match_features(orb, matcher, prev_img, curr_img)
            if matched is None:
                prev_img = curr_img
                continue
            pts1, pts2 = matched
            E, _ = cv2.findEssentialMat(pts1, pts2, K, method=cv2.RANSAC, prob=0.999, threshold=1.0)
            if E is None:
                prev_img = curr_img
                continue
            _, R, t, mask_pose = cv2.recoverPose(E, pts1, pts2, K)
            new_R = global_R @ R
            new_t = global_t + global_R @ t
            P1 = K @ np.hstack([global_R, global_t])
            P2 = K @ np.hstack([new_R, new_t])
            inliers = mask_pose.ravel().astype(bool)
            if inliers.sum() >= 8:
                pts4d = cv2.triangulatePoints(P1, P2, pts1[inliers].T, pts2[inliers].T)
                pts3d = (pts4d[:3] / pts4d[3]).T
                proj, _ = cv2.projectPoints(pts3d, cv2.Rodrigues(global_R)[0], global_t, K, None)
                err = np.linalg.norm(proj.reshape(-1, 2) - pts1[inliers], axis=1)
                good = (pts3d[:, 2] > 0) & (err < REPROJ_ERROR_THRESHOLD)
                all_points.append(pts3d[good][:MAX_POINTS_PER_PAIR])
            global_R, global_t = new_R, new_t
            camera_count += 1
            prev_img = curr_img

        if not all_points:
            raise ReconstructionError("어떤 프레임 쌍에서도 쓸 만한 3D 점을 못 얻었습니다.")

        cloud = _remove_outliers(np.vstack(all_points))
        if len(cloud) == 0:
            raise ReconstructionError("이상치를 걸러내고 나니 남은 점이 없습니다.")
        return cloud, camera_count


def _remove_outliers(cloud, keep_percentile=65.0):
    median = np.median(cloud, axis=0)
    dist = np.linalg.norm(cloud - median, axis=1)
    return cloud[dist <= np.percentile(dist, keep_percentile)]


def generate_mesh(cloud, timeout=150):
    if not _MESH_VENV_PYTHON or not Path(_MESH_VENV_PYTHON).exists():
        return None, None, None
    with tempfile.NamedTemporaryFile(suffix=".npy", delete=False) as f:
        cloud_path = Path(f.name)
    try:
        np.save(cloud_path, cloud)
        result = subprocess.run(
            [_MESH_VENV_PYTHON, str(_MESH_SCRIPT), str(cloud_path)],
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            return None, None, None
        data = json.loads(result.stdout)
        if "error" in data:
            return None, None, None
        return np.array(data["vertices"]), np.array(data["faces"], dtype=int), data.get("method")
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return None, None, None
    finally:
        cloud_path.unlink(missing_ok=True)
