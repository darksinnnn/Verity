"""
matching_engine/solver.py

Core DP-based subset-sum solver.

Problem: given a target amount T (a bank credit, in paise) and a pool of
candidate payment net amounts, find the subset S whose sum falls within
[T - epsilon_low, T + epsilon_high].

Key design decisions (per Architecture.md §4):
  - All arithmetic is over integers in paise. Never floats.
  - Date-window and counterparty pruning is applied FIRST to shrink the
    candidate pool before running subset-sum, to keep complexity in check.
  - DP runs over the pruned pool only.
  - 1:1 and N:1 (1 bank credit : many payments) are supported.
  - 1:N (many bank credits : 1 payment) is handled by the caller iterating
    over bank credits independently.
  - N:N is explicitly out of scope for v1.
"""

from __future__ import annotations

DATE_WINDOW_DAYS = 7   # max days between payment and bank credit to be considered a match


def _within_date_window(payment_date: str, credit_date: str, window_days: int = DATE_WINDOW_DAYS) -> bool:
    """
    Returns True if the bank credit date is within window_days after the payment date.
    Dates are ISO-format strings.
    """
    from datetime import datetime
    fmt = "%Y-%m-%dT%H:%M:%S"
    try:
        p = datetime.fromisoformat(payment_date)
        c = datetime.fromisoformat(credit_date)
    except ValueError:
        # Fallback: strip time component if needed
        p = datetime.strptime(payment_date[:10], "%Y-%m-%d")
        c = datetime.strptime(credit_date[:10], "%Y-%m-%d")
    delta = (c - p).days
    return 0 <= delta <= window_days


def prune_candidates(
    candidates: list[dict],
    credit_date: str,
    window_days: int = DATE_WINDOW_DAYS,
) -> list[dict]:
    """
    Apply date-window pruning FIRST.
    Each candidate dict must have keys: 'payment_id', 'net_amount_paise', 'captured_at'.
    Returns a filtered list.
    """
    return [
        c for c in candidates
        if _within_date_window(c['captured_at'], credit_date, window_days)
    ]


def subset_sum_dp(
    candidates: list[dict],
    target_paise: int,
    lower_bound: int,
    upper_bound: int,
) -> list[str] | None:
    """
    DP subset-sum solver over integer paise.

    Finds the subset of candidates whose net_amount_paise sum falls within
    [lower_bound, upper_bound].

    Returns a list of payment_ids that form the matching subset, or None if
    no such subset exists.

    Complexity: O(N * target) where N = len(candidates) and target is measured
    in paise. For 50-80 records and amounts up to ~₹5L (50_000_000 paise),
    this can be large. We bound the DP range to [lower_bound, upper_bound]
    and cap the pool at the pruned candidate set only — which the caller
    ensures is small before calling this.

    N:N is NOT attempted here. If the pruned pool is larger than 25 candidates,
    we log a warning and limit to the 25 smallest (a practical safety valve
    for this scale, with the limitation documented).
    """
    MAX_CANDIDATES = 25
    if len(candidates) > MAX_CANDIDATES:
        candidates = sorted(candidates, key=lambda c: c['net_amount_paise'])[:MAX_CANDIDATES]

    n = len(candidates)
    if n == 0:
        return None

    # DP table: dp[amount] = list of payment_ids that sum to this amount.
    # We track reachable amounts in the window [lower_bound, upper_bound].
    # To avoid a huge dict for large targets, we shift amounts by lower_bound.
    window_size = upper_bound - lower_bound

    # dp maps (sum_of_subset) -> (list_of_payment_ids | sentinel)
    # We use a dict to track only reachable sums, which is sparse.
    # Key: sum in paise (absolute).  Value: frozenset of payment_ids.
    reachable: dict[int, tuple[str, ...]] = {0: ()}

    for cand in candidates:
        net = cand['net_amount_paise']
        pid = cand['payment_id']
        # Iterate in reverse over current reachable sums to avoid reusing
        # the same candidate twice (standard 0/1 knapsack pattern).
        new_reachable: dict[int, tuple[str, ...]] = {}
        for current_sum, current_ids in reachable.items():
            new_sum = current_sum + net
            if new_sum > upper_bound:
                continue  # pruned: already over the ceiling
            candidate_tuple = current_ids + (pid,)
            if new_sum not in reachable and new_sum not in new_reachable:
                new_reachable[new_sum] = candidate_tuple
            elif new_sum in reachable and len(candidate_tuple) < len(reachable[new_sum]):
                reachable[new_sum] = candidate_tuple
            elif new_sum in new_reachable and len(candidate_tuple) < len(new_reachable[new_sum]):
                new_reachable[new_sum] = candidate_tuple
        reachable.update(new_reachable)

    # Find the best matching sum within [lower_bound, upper_bound].
    # Tie-breaking: prefer closer sum to target; if tied, prefer fewer payments (Occam's razor: 1:1 > N:1).
    best_sum = None
    best_ids = None
    for s, ids in reachable.items():
        if lower_bound <= s <= upper_bound and len(ids) > 0:
            delta = abs(s - target_paise)
            if best_sum is None:
                best_sum = s
                best_ids = ids
            else:
                best_delta = abs(best_sum - target_paise)
                if delta < best_delta or (delta == best_delta and len(ids) < len(best_ids)):
                    best_sum = s
                    best_ids = ids

    if best_ids is None:
        return None

    return list(best_ids)
