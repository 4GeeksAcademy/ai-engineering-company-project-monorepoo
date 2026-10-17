import json
import statistics
import time

from fastapi.testclient import TestClient

import main


def measure(row_count: int, repetitions: int = 20) -> list[dict[str, object]]:
    main.catalog = main.PublicCatalog()
    for family in ("menu", "locations"):
        rows = main.catalog.menu if family == "menu" else main.catalog.locations
        seed = list(rows)
        rows[:] = [
            {**seed[index % len(seed)], "id": f"synthetic-{index}", "name": f"Sample {index:06d}"}
            for index in range(row_count)
        ]
    results = []
    with TestClient(main.app) as client:
        for endpoint in ("menu", "locations"):
            cold = []
            hot = []
            for _ in range(repetitions):
                main.catalog.entries.clear()
                start = time.perf_counter()
                response = client.get(f"/{endpoint}?country=CO")
                cold.append((time.perf_counter() - start) * 1000)
                assert response.headers["X-Cache"] == "MISS"
                start = time.perf_counter()
                response = client.get(f"/{endpoint}?country=CO")
                hot.append((time.perf_counter() - start) * 1000)
                assert response.headers["X-Cache"] == "HIT"
            results.append({
                "endpoint": endpoint,
                "rows": row_count,
                "repetitions": repetitions,
                "cold_median_ms": round(statistics.median(cold), 3),
                "hit_median_ms": round(statistics.median(hot), 3),
            })
    return results


if __name__ == "__main__":
    print(json.dumps(measure(2) + measure(10000), indent=2))