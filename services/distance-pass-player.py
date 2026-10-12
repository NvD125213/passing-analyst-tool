import json
import math
import sys
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "output"
# Đổi tên thư mục này khi muốn tính folder khác. Mỗi lần chạy chỉ một folder.
DATA_DIR = OUTPUT_DIR / "wirtz-match-statitics-epl"
# Số trận đưa vào phép tính. None nghĩa là lấy hết file JSON trong folder.
MATCH_LIMIT = 4


def calculate_distance_pass_player(pass_data):
    start = pass_data["playerCoordinates"]
    end = pass_data["passEndCoordinates"]

    dx = end["x"] - start["x"]
    dy = end["y"] - start["y"]

    return math.sqrt(dx**2 + dy**2)


def _pass_distances(pass_data: dict) -> tuple[float, bool] | None:
    """Bỏ đường chuyền dài. Trả về khoảng cách và cờ thành công."""
    if pass_data.get("isLongBall") is True:
        return None
    if (
        pass_data.get("eventActionType") != "pass"
        or not pass_data.get("playerCoordinates")
        or not pass_data.get("passEndCoordinates")
    ):
        return None
    return calculate_distance_pass_player(pass_data), pass_data.get("outcome") is True


def _summary(label: str, file_results: list[dict], all_distances: list[float], successful_distances: list[float]) -> dict:
    total_distance = sum(all_distances)
    total_passes = len(all_distances)
    average_passes = total_passes / len(file_results)
    average_distance = total_distance / total_passes
    successful_average = (
        sum(successful_distances) / len(successful_distances) if successful_distances else None
    )
    success_text = "n/a" if successful_average is None else f"{successful_average:.2f} m"

    print("--------------------------------")
    print(label)
    print(f"Matches: {len(file_results)}")
    print(f"Total distance: {total_distance:.2f} m")
    print(f"Total passes: {total_passes}")
    print(f"AvgTotal passes: {average_passes:.2f}")
    print(f"AvgDistance pass: {average_distance:.2f} m")
    print(f"Total passes success: {len(successful_distances)}")
    print(f"AvgDistance pass success (outcome == true): {success_text}")

    return {
        "label": label,
        "matches": len(file_results),
        "total_distance": total_distance,
        "total_passes": total_passes,
        "average_passes": average_passes,
        "average_distance": average_distance,
        "successful_passes": len(successful_distances),
        "successful_average_distance": successful_average,
    }


def _collect_folder(data_dir: Path, match_limit: int | None = MATCH_LIMIT) -> dict | None:
    file_results = []
    all_distances = []
    successful_distances = []
    excluded_long_balls = 0
    json_files = sorted(data_dir.glob("*.json"))
    if match_limit is not None:
        json_files = json_files[:match_limit]
    print(f"Số trận tính: {len(json_files)}")

    for file_path in json_files:
        with open(file_path, "r", encoding="utf-8") as file:
            data = json.load(file)

        distances = []
        match_successful_distances = []
        for pass_data in data.get("passes", []):
            if pass_data.get("isLongBall") is True:
                excluded_long_balls += 1
            measured = _pass_distances(pass_data)
            if measured is None:
                continue
            distance, is_successful = measured
            distances.append(distance)
            if is_successful:
                match_successful_distances.append(distance)

        if not distances:
            continue

        file_average = sum(distances) / len(distances)
        successful_average = (
            sum(match_successful_distances) / len(match_successful_distances)
            if match_successful_distances
            else None
        )
        file_results.append(
            {
                "file": file_path.name,
                "pass_count": len(distances),
                "average_distance": file_average,
                "successful_pass_count": len(match_successful_distances),
                "successful_average_distance": successful_average,
            }
        )
        all_distances.extend(distances)
        successful_distances.extend(match_successful_distances)

        print(f"AvgDistance trận đấu {file_path.name}: {file_average:.2f}m")
        print(f"Total distance: {sum(distances):.2f}")
        print(f"Total passes: {len(distances)}")
        if successful_average is None:
            print("AvgDistance pass success (outcome == true): không có đường chuyền thành công")
        else:
            print(f"AvgDistance pass success (outcome == true): {successful_average:.2f}m")
            print(f"Total passes success: {len(match_successful_distances)}")
        print("-" * 50)

    if not all_distances:
        print(f"Không có đường chuyền trong {data_dir.name}")
        return None

    print(f"Đã loại chuyền dài (isLongBall = true): {excluded_long_balls}")
    return _summary(data_dir.name, file_results, all_distances, successful_distances) | {
        "file_results": file_results,
        "all_distances": all_distances,
        "successful_distances": successful_distances,
    }


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if not DATA_DIR.is_dir():
        raise SystemExit(f"Không thấy thư mục {DATA_DIR}")
    print("=" * 50)
    print(DATA_DIR.name)
    print("=" * 50)
    _collect_folder(DATA_DIR, MATCH_LIMIT)
