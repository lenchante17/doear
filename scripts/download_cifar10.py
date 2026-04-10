from __future__ import annotations

from pathlib import Path
import pickle
import tarfile
import urllib.request
import warnings

import numpy as np


ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw_downloads"
CIFAR10_SOURCE = RAW_DIR / "cifar-10-python.tar.gz"
CIFAR10_TARGET = ROOT / "data" / "cifar10" / "cifar10.npz"
CIFAR10_URL = "https://www.cs.toronto.edu/~kriz/cifar-10-python.tar.gz"


def ensure_download(url: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        print(f"reuse {target}")
        return
    print(f"download {url} -> {target}")
    urllib.request.urlretrieve(url, target)


def _load_cifar_batch(archive: tarfile.TarFile, member_name: str) -> tuple[np.ndarray, np.ndarray]:
    member = archive.getmember(member_name)
    with archive.extractfile(member) as handle:
        if handle is None:
            raise RuntimeError(f"Could not read {member_name} from CIFAR-10 archive.")
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message=r"dtype\(\): align should be passed as Python or NumPy boolean.*",
            )
            payload = pickle.load(handle, encoding="bytes")
    data = payload[b"data"].reshape((-1, 3, 32, 32)).transpose((0, 2, 3, 1)).astype(np.uint8)
    labels = np.asarray(payload[b"labels"], dtype=np.int64)
    return data, labels


def build_cifar10_dataset() -> None:
    ensure_download(CIFAR10_URL, CIFAR10_SOURCE)
    CIFAR10_TARGET.parent.mkdir(parents=True, exist_ok=True)

    train_images: list[np.ndarray] = []
    train_labels: list[np.ndarray] = []
    with tarfile.open(CIFAR10_SOURCE, "r:gz") as archive:
        for batch_index in range(1, 6):
            x_part, y_part = _load_cifar_batch(archive, f"cifar-10-batches-py/data_batch_{batch_index}")
            train_images.append(x_part)
            train_labels.append(y_part)
        x_test, y_test = _load_cifar_batch(archive, "cifar-10-batches-py/test_batch")

    x_train = np.concatenate(train_images, axis=0)
    y_train = np.concatenate(train_labels, axis=0)
    x = np.concatenate([x_train, x_test], axis=0)
    y = np.concatenate([y_train, y_test], axis=0)
    np.savez_compressed(CIFAR10_TARGET, x=x, y=y)
    print(f"write {CIFAR10_TARGET} {x.shape} {y.shape}")


def main() -> int:
    build_cifar10_dataset()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
