import json
import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from mplsoccer import VerticalPitch

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "output"
IMG_DIR = Path(__file__).resolve().parents[1] / "img" / "map"
# Một hoặc nhiều folder. Nhiều folder được gộp chung một bản đồ.
DATA_DIRS = [
    OUTPUT_DIR / "wirtz-match-statitics-wc",
    OUTPUT_DIR / "wirtz-match-statitics-nation-league",
    OUTPUT_DIR / "wirtz-match-statitics-international",

]
# Số trận đưa vào phép tính. None nghĩa là lấy hết file JSON trong folder.
MATCH_LIMIT = 20

# SofaScore: x tăng về phía khung thành đối phương, y là chiều ngang sân (0-100).
OPPONENT_HALF_MIN_X = 50
# Đường chuyền phải đi lên, điểm kết thúc có x lớn hơn điểm bắt đầu.
REQUIRE_UPWARD = True
# Mỗi vùng chỉ vẽ hướng xuất hiện nhiều nhất. Bỏ hướng ít hơn ngưỡng này.
MIN_VECTOR_COUNT = 5
ANGLE_BIN_DEGREES = 45

DEPTH_ZONES = (
    (50, 66.67, "Giữa sân đối phương"),
    (66.67, 83.33, "1/3 sân cuối"),
    (83.33, 100.01, "Vùng cấm"),
)
WIDTH_ZONES = (
    (0, 33.34, "Hành lang trái"),
    (33.34, 66.67, "Trung lộ"),
    (66.67, 100.01, "Hành lang phải"),
)


def pass_length(pass_data: dict) -> float:
    start = pass_data["playerCoordinates"]
    end = pass_data["passEndCoordinates"]
    dx = end["x"] - start["x"]
    dy = end["y"] - start["y"]
    return math.sqrt(dx**2 + dy**2)


def _zone_label(value: float, zones: tuple[tuple[float, float, str], ...]) -> str:
    for start, end, name in zones:
        if start <= value < end:
            return name
    return "Ngoài vùng"


def pitch_zone(pass_data: dict) -> str:
    start = pass_data["playerCoordinates"]
    depth = _zone_label(start["x"], DEPTH_ZONES)
    width = _zone_label(start["y"], WIDTH_ZONES)
    return f"{width} / {depth}"


def is_opponent_half_upward(pass_data: dict) -> bool:
    if pass_data.get("eventActionType") != "pass":
        return False
    start = pass_data.get("playerCoordinates")
    end = pass_data.get("passEndCoordinates")
    if not start or not end:
        return False
    if start["x"] <= OPPONENT_HALF_MIN_X:
        return False
    if REQUIRE_UPWARD and end["x"] <= start["x"]:
        return False
    return True


def _empty_bucket() -> dict:
    return {"success": [], "fail": []}


def _add_pass(bucket: dict, pass_data: dict) -> None:
    start = pass_data["playerCoordinates"]
    end = pass_data["passEndCoordinates"]
    length = pass_length(pass_data)
    key = "success" if pass_data.get("outcome") is True else "fail"
    bucket[key].append(
        {
            "length": length,
            "zone": pitch_zone(pass_data),
            "file": pass_data["_file"],
            "outcome": key,
            "x": start["x"],
            "y": start["y"],
            "end_x": end["x"],
            "end_y": end["y"],
        }
    )


def _rate(count: int, total: int) -> str:
    if total == 0:
        return "n/a"
    return f"{count / total * 100:.1f}%"


def _average(lengths: list[float]) -> str:
    if not lengths:
        return "n/a"
    return f"{sum(lengths) / len(lengths):.2f}"


def _print_type(title: str, bucket: dict) -> None:
    success = bucket["success"]
    fail = bucket["fail"]
    total = len(success) + len(fail)
    all_lengths = [item["length"] for item in success + fail]
    print(title)
    print(f"  Tổng: {total}")
    print(f"  Thành công: {len(success)} ({_rate(len(success), total)})")
    print(f"  Hỏng: {len(fail)} ({_rate(len(fail), total)})")
    print(f"  Độ dài trung bình: {_average(all_lengths)}")
    print(f"  Độ dài trung bình thành công: {_average([item['length'] for item in success])}")
    print(f"  Độ dài trung bình hỏng: {_average([item['length'] for item in fail])}")
    print("  Zone thực hiện:")
    zone_counts: dict[str, dict[str, int]] = {}
    for outcome, items in (("thành công", success), ("hỏng", fail)):
        for item in items:
            zone_counts.setdefault(item["zone"], {"thành công": 0, "hỏng": 0})
            zone_counts[item["zone"]][outcome] += 1
    if not zone_counts:
        print("    Không có đường chuyền")
        return
    for zone, counts in sorted(zone_counts.items()):
        zone_total = counts["thành công"] + counts["hỏng"]
        print(
            f"    {zone}: {zone_total} "
            f"(thành công {counts['thành công']}, hỏng {counts['hỏng']})"
        )


def _match_files(data_dir: Path, match_limit: int | None) -> list[Path]:
    json_files = sorted(data_dir.glob("*.json"))
    if match_limit is not None:
        json_files = json_files[:match_limit]
    return json_files


def analyze_folders(data_dirs: list[Path], match_limit: int | None = MATCH_LIMIT) -> None:
    short_passes = _empty_bucket()
    long_passes = _empty_bucket()
    used_dirs = []
    match_count = 0

    for data_dir in data_dirs:
        if not data_dir.is_dir():
            print(f"Không thấy thư mục {data_dir}")
            continue
        json_files = _match_files(data_dir, match_limit)
        used_dirs.append(data_dir)
        match_count += len(json_files)
        print(f"{data_dir.name}: {len(json_files)} trận")
        for file_path in json_files:
            with open(file_path, "r", encoding="utf-8") as file:
                data = json.load(file)
            for pass_data in data.get("passes", []):
                if not is_opponent_half_upward(pass_data):
                    continue
                pass_data = {**pass_data, "_file": file_path.name}
                if pass_data.get("isLongBall") is True:
                    _add_pass(long_passes, pass_data)
                else:
                    _add_pass(short_passes, pass_data)

    if not used_dirs:
        raise SystemExit("Không có folder dữ liệu để tính.")

    selected = (
        len(short_passes["success"])
        + len(short_passes["fail"])
        + len(long_passes["success"])
        + len(long_passes["fail"])
    )
    print(f"Đường chuyền nửa sân đối phương, đi lên: {selected}")
    print("-" * 50)
    _print_type("Chuyền ngắn", short_passes)
    print("-" * 50)
    _print_type("Chuyền dài (isLongBall = true)", long_passes)
    image_path = save_pitch_map(used_dirs, short_passes, long_passes, match_count)
    print(f"Đã lưu bản đồ: {image_path}")


def _pass_angle(item: dict) -> float:
    dx = item["end_x"] - item["x"]
    dy = item["end_y"] - item["y"]
    return math.degrees(math.atan2(dy, dx))


def _dominant_vectors(items: list[dict], min_count: int) -> list[dict]:
    """Mỗi zone giữ một hướng (cụm góc) có nhiều đường chuyền nhất."""
    grouped: dict[tuple[str, int], list[dict]] = {}
    for item in items:
        sector = math.floor((_pass_angle(item) + ANGLE_BIN_DEGREES / 2) / ANGLE_BIN_DEGREES)
        grouped.setdefault((item["zone"], sector), []).append(item)

    best_by_zone: dict[str, list[dict]] = {}
    for (zone, _sector), group in grouped.items():
        current = best_by_zone.get(zone)
        if current is None or len(group) > len(current):
            best_by_zone[zone] = group

    vectors = []
    for group in best_by_zone.values():
        if len(group) < min_count:
            continue
        start_x = sum(item["x"] for item in group) / len(group)
        start_y = sum(item["y"] for item in group) / len(group)
        mean_dx = sum(item["end_x"] - item["x"] for item in group) / len(group)
        mean_dy = sum(item["end_y"] - item["y"] for item in group) / len(group)
        success = sum(item["outcome"] == "success" for item in group)
        lengths = [item["length"] for item in group]
        vectors.append(
            {
                "zone": group[0]["zone"],
                "x": start_x,
                "y": start_y,
                "end_x": start_x + mean_dx,
                "end_y": start_y + mean_dy,
                "count": len(group),
                "success": success,
                "average_length": sum(lengths) / len(lengths),
            }
        )
    return vectors


def _label_rotation(ax, x0: float, y0: float, x1: float, y1: float) -> float:
    """Góc chữ trên màn hình, cùng hướng với mũi tên của sân dọc."""
    start = ax.transData.transform((y0, x0))
    end = ax.transData.transform((y1, x1))
    angle = math.degrees(math.atan2(end[1] - start[1], end[0] - start[0]))
    if angle > 90:
        angle -= 180
    elif angle < -90:
        angle += 180
    return angle


def _draw_flow(pitch: VerticalPitch, ax, vectors: list[dict], color: str) -> None:
    if not vectors:
        return
    counts = [vector["count"] for vector in vectors]
    widest = max(counts)
    for vector in vectors:
        pitch.arrows(
            vector["x"],
            vector["y"],
            vector["end_x"],
            vector["end_y"],
            ax=ax,
            color=color,
            width=1.6 + 3.4 * vector["count"] / widest,
            headwidth=3.5,
            headlength=4,
            alpha=0.95,
        )
        success_rate = vector["success"] / vector["count"] * 100
        rotation = _label_rotation(ax, vector["x"], vector["y"], vector["end_x"], vector["end_y"])
        labels = (
            (str(vector["count"]), "#FFFFFF"),
            (f"{success_rate:.0f}%", "#FFD166"),
            (f"{vector['average_length']:.1f}", "#7AD7FF"),
        )
        for index, (text, label_color) in enumerate(labels):
            along = 0.48 + index * 0.18
            label_x = vector["x"] + (vector["end_x"] - vector["x"]) * along
            label_y = vector["y"] + (vector["end_y"] - vector["y"]) * along
            pitch.text(
                label_x,
                label_y,
                text,
                ax=ax,
                rotation=rotation,
                rotation_mode="anchor",
                ha="center",
                va="center",
                color=label_color,
                fontsize=9,
                fontweight="bold",
                bbox={"boxstyle": "round,pad=0.15", "fc": "#0e1712", "ec": "none", "alpha": 0.88},
            )


def _map_name(data_dirs: list[Path]) -> str:
    if len(data_dirs) == 1:
        return data_dirs[0].name
    return " + ".join(data_dir.name.removeprefix("wirtz-match-statitics-") for data_dir in data_dirs)


def save_pitch_map(data_dirs: list[Path], short_passes: dict, long_passes: dict, match_count: int) -> Path:
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    plt.rcParams["font.family"] = "Segoe UI"
    pitch = VerticalPitch(
        pitch_type="opta",
        half=True,
        pitch_color="#122015",
        line_color="#f2f2f2",
        linewidth=1.4,
        pad_bottom=1,
    )
    fig, pitch_ax = pitch.draw(figsize=(12, 8), tight_layout=False)
    fig.patch.set_facecolor("#0e1712")
    fig.subplots_adjust(bottom=0.1)

    for depth in (66.67, 83.33):
        pitch.lines(depth, 0, depth, 100, ax=pitch_ax, color="#f2f2f2", lw=0.8, alpha=0.35, ls="--")
    for width in (33.34, 66.67):
        pitch.lines(50, width, 100, width, ax=pitch_ax, color="#f2f2f2", lw=0.8, alpha=0.35, ls="--")

    short_vectors = _dominant_vectors(short_passes["success"] + short_passes["fail"], MIN_VECTOR_COUNT)
    long_vectors = _dominant_vectors(long_passes["success"] + long_passes["fail"], min_count=2)
    _draw_flow(pitch, pitch_ax, short_vectors, "#3DDC97")
    _draw_flow(pitch, pitch_ax, long_vectors, "#4DA3FF")

    legend = [
        Line2D([0], [0], color="#3DDC97", lw=2.5, label="Short Pass"),
        Line2D([0], [0], color="#4DA3FF", lw=2.5, label="Long Pass"),
        Line2D([0], [0], color="#FFFFFF", lw=2.5, label="Total Pass Count"),
        Line2D([0], [0], color="#FFD166", lw=2.5, label="TotPassSuc%"),
        Line2D([0], [0], color="#7AD7FF", lw=2.5, label="AvgDisPass"),
    ]
    fig.legend(
        handles=legend,
        loc="lower center",
        frameon=False,
        fontsize=11,
        labelcolor="white",
        ncol=5,
        bbox_to_anchor=(0.5, 0.02),
    )
    destination = IMG_DIR / f"{_map_name(data_dirs)}.png"
    fig.savefig(destination, dpi=200, bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    print(f"Số trận gộp: {match_count}")
    return destination


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print("=" * 50)
    print(" + ".join(data_dir.name for data_dir in DATA_DIRS))
    print("=" * 50)
    analyze_folders(DATA_DIRS, MATCH_LIMIT)
