def rrf_fusion(*rank_lists: list, k: int = 20):
    """
    RRF fusion for any number of rank lists
    """
    c = 10

    # Convert each rank list into a dictionary of {case_id: rank}
    rank_dicts = [{case_id: rank for rank, case_id in enumerate(rank_list)} for rank_list in rank_lists]

    # Merge all case IDs from all rank lists
    all_ids = set()
    for rank_dict in rank_dicts:
        all_ids.update(rank_dict.keys())

    # Calculate RRF scores for each case ID
    all_scores = {}
    for case_id in all_ids:
        score = sum(1 / (rank_dict.get(case_id, len(rank_dict)) + c) for rank_dict in rank_dicts)
        all_scores[case_id] = score

    # Sort all_scores by their values
    sorted_scores = sorted(all_scores.items(), key=lambda x: x[1], reverse=True)

    # Get the top k case IDs
    top_k_case_ids = [case_id for case_id, _ in sorted_scores[:k]]
    return top_k_case_ids