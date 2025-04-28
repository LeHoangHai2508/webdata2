import pandas as pd
from ecom.models import Orders


def load_transactions_from_csv(csv_path: str) -> list[set]:
    """
    Đọc file CSV và trả về danh sách các transaction.
    Mỗi transaction là một set các item.
    File CSV cần có 2 cột: 'Transaction' và 'Item'.
    """
    df = pd.read_csv(csv_path)
    grouped = df.groupby('Transaction')['Item'].apply(set)
    return grouped.tolist()


def load_transactions_from_db() -> list[set]:
    """
    Lấy giao dịch trực tiếp từ model Orders.
    Mỗi Orders chứa một product. Nhóm theo order_id để tạo mỗi transaction là tập product.
    """
    tx_dict: dict[int, set] = {}
    # Sử dụng select_related để tối ưu truy vấn
    for o in Orders.objects.select_related('product').all():
        oid = o.id
        pname = o.product.name if hasattr(o.product, 'name') else str(o.product.id)
        tx_dict.setdefault(oid, set()).add(pname)
    return list(tx_dict.values())


def get_frequent_items(transactions: list[set], min_support: int) -> dict[str, int]:
    counts: dict[str, int] = {}
    for t in transactions:
        for item in t:
            counts[item] = counts.get(item, 0) + 1
    return {item: c for item, c in counts.items() if c >= min_support}


def mafia_recursive(
    transactions: list[set],
    head_items: set,
    min_support: int
) -> list[set]:
    tail_counts = get_frequent_items(transactions, min_support)
    maximal_itemsets: list[set] = []

    for item in tail_counts:
        new_head = head_items | {item}
        proj_trans = [t for t in transactions if new_head.issubset(t)]
        maximal_itemsets.extend(
            mafia_recursive(proj_trans, new_head, min_support)
        )

    if not tail_counts:
        maximal_itemsets.append(head_items)

    return maximal_itemsets


def run_mafia(
    min_support: int,
    csv_path: str | None = None
) -> list[set]:
    """
    Hàm chính để chạy MAFIA.
    Nếu csv_path được truyền, sẽ load từ CSV, ngược lại load từ DB.
    """
    if csv_path:
        transactions = load_transactions_from_csv(csv_path)
    else:
        transactions = load_transactions_from_db()
    return mafia_recursive(transactions, set(), min_support)