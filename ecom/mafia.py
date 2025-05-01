from collections import defaultdict
from itertools import combinations


def build_tidsets(transactions):
    """
    Chuyển giao dịch sang dạng TID-sets (item -> tập các transaction ID chứa item).
    transactions: list of transaction lists.
    Trả về dict {item: set(tid)}
    """
    tidsets = defaultdict(set)
    for tid, transaction in enumerate(transactions):
        for item in transaction:
            tidsets[item].add(tid)
    return tidsets


def mafia(head, tail, tidsets, minsup, MFI, parent_tids):
    """
    Triển khai MAFIA DFS với HUT và PEP pruning.
    head: tập mục hiện tại (set)
    tail: danh sách item mở rộng
    tidsets: dict item -> set(tid)
    minsup: ngưỡng hỗ trợ tối thiểu (int)
    MFI: list kết quả (maximal frequent itemsets)
    parent_tids: tập tid của head
    """
    # HUT Pruning: nếu head ∪ tail đã bị chứa trong một MFI
    hut = head | set(tail)
    if any(mfi.issuperset(hut) for mfi in MFI):
        return

    # Xác định các extension frequent
    extensions = []
    for item in tail:
        tids_new = tidsets[item] & parent_tids
        if len(tids_new) >= minsup:
            extensions.append((item, tids_new))

    # Sắp xếp PEP theo support tăng dần
    extensions.sort(key=lambda x: len(x[1]))

    extended = False
    for i, (item, tids_i) in enumerate(extensions):
        new_tail = [it for it, _ in extensions[i+1:]]
        # PEP Pruning: nếu không thu hẹp tidsets, bỏ qua
        if tids_i == parent_tids:
            continue
        mafia(head | {item}, new_tail, tidsets, minsup, MFI, tids_i)
        extended = True

    # Nếu không mở rộng thêm, head là maximal
    if not extended:
        if not any(existing.issuperset(head) for existing in MFI):
            MFI.append(head)


def find_maximal_itemsets(transactions, min_support=0.3):
    """
    Giao diện tìm maximal frequent itemsets qua MAFIA.
    transactions: list of lists
    min_support: ngưỡng (0-1)
    Trả về list of frozenset
    """
    n = len(transactions)
    minsup = int(min_support * n)
    tidsets = build_tidsets(transactions)
    items = sorted(tidsets.keys())
    all_tids = set(range(n))
    MFI = []
    mafia(set(), items, tidsets, minsup, MFI, all_tids)
    return [frozenset(m) for m in MFI]


def generate_association_rules(transactions, min_support=0.3, min_confidence=0.6):
    """
    Sinh luật kết hợp từ maximal itemsets.
    transactions: list of lists
    min_support: ngưỡng support (0-1)
    min_confidence: ngưỡng confidence (0-1)
    Trả về list các luật (antecedent, consequent, support, confidence, lift)
    """
    n = len(transactions)
    tidsets = build_tidsets(transactions)

    # Lấy maximal itemsets và tính support cho mọi subset
    maximal_sets = find_maximal_itemsets(transactions, min_support)
    support = {}
    frequent_sets = set()
    for mset in maximal_sets:
        for r in range(1, len(mset)+1):
            for subset in combinations(mset, r):
                S = frozenset(subset)
                if S not in support:
                    # tính support dựa trên TID-sets
                    tids = set.intersection(*(tidsets[item] for item in S))
                    support[S] = len(tids) / n
                frequent_sets.add(S)

    # Sinh luật
    rules = []
    for itemset in frequent_sets:
        if len(itemset) < 2:
            continue
        for r in range(1, len(itemset)):
            for A in combinations(itemset, r):
                A = frozenset(A)
                B = itemset - A
                supp_AB = support.get(itemset, 0)
                supp_A = support.get(A, 0)
                supp_B = support.get(B, 0)
                if supp_A == 0:
                    continue
                conf = supp_AB / supp_A
                if conf < min_confidence:
                    continue
                lift = conf / supp_B if supp_B > 0 else 0
                rules.append((A, B, supp_AB, conf, lift))

    # Sắp xếp luật theo confidence giảm dần
    rules.sort(key=lambda x: x[3], reverse=True)
    return rules


def find_maximal_itemsets_and_rules(transactions, min_support=0.3, min_confidence=0.6):
    """
    Trả về maximal itemsets và luật kết hợp.
    """
    maximal = find_maximal_itemsets(transactions, min_support)
    rules = generate_association_rules(transactions, min_support, min_confidence)
    return maximal, rules
